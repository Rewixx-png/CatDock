import logging
import asyncio
import re
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InputMediaPhoto

from config import SERVERS
from utils.filters import IsAdmin
from roles import UserRole
from keyboards.admin import get_htop_server_keyboard, get_htop_refresh_keyboard
from utils.ssh_runner import run_command_on_server
from utils.htop_graph import generate_htop_image

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

@router.message(Command("htop"))
async def cmd_htop_start(message: types.Message):
    await message.answer(
        "🖥 <b>Мониторинг ресурсов (HTOP)</b>\n\nВыберите сервер для анализа:",
        reply_markup=get_htop_server_keyboard()
    )

@router.callback_query(F.data == "admin_htop_menu")
async def back_to_htop_menu(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except: pass
    await callback.message.answer(
        "🖥 <b>Мониторинг ресурсов (HTOP)</b>\n\nВыберите сервер для анализа:",
        reply_markup=get_htop_server_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "delete_message")
async def delete_msg(callback: types.CallbackQuery):
    try: await callback.message.delete()
    except: pass
    await callback.answer()

def parse_proc_stat(stdout: str) -> dict:
    cpus = {}
    for line in stdout.splitlines():
        if line.startswith('cpu'):
            parts = line.split()
            if len(parts) < 5: continue
            cpu_name = parts[0]
            try:
                values = [int(x) for x in parts[1:]]
                total = sum(values)
                idle = values[3]
                cpus[cpu_name] = {'total': total, 'idle': idle}
            except ValueError:
                continue
    return cpus

@router.callback_query(F.data.startswith("htop_select_server:"))
@router.callback_query(F.data.startswith("htop_refresh:"))
async def htop_process(callback: types.CallbackQuery, bot: Bot):
    action = callback.data.split(":")[0]
    server_id = callback.data.split(":")[1]
    server_name = SERVERS.get(server_id, {}).get('name', server_id)

    if "refresh" not in action:
        try:
            await callback.message.edit_text(f"⏳ <b>{server_name}:</b> Сбор данных...")
        except TelegramBadRequest: pass
    else:
        await callback.answer("🔄 Обновление данных...", show_alert=False)

    SPLIT_MARKER = "###SPLIT_HTOP###"

    remote_script = (
        "cat /proc/stat; "
        f"echo '{SPLIT_MARKER}'; "
        "sleep 1; "
        "cat /proc/stat; "
        f"echo '{SPLIT_MARKER}'; "
        "LC_ALL=C free -m; "
        f"echo '{SPLIT_MARKER}'; "
        "LC_ALL=C uptime; "
        f"echo '{SPLIT_MARKER}'; "
        "ps -A --no-headers | wc -l; "
        "ps -eLf --no-headers | wc -l; "
        "grep procs_running /proc/stat | awk '{print $2}'; "
        f"echo '{SPLIT_MARKER}'; "
        "LC_ALL=C ps -Ao pid,user,pri,ni,vsz,rss,s,pcpu,pmem,time,args --sort=-pcpu --width 1000 | head -n 4"
    )

    try:
        result = await run_command_on_server(server_id, remote_script, timeout=20)

        if result.exit_status != 0:
            raise Exception(f"Script error: {result.stderr}")

        parts = [p.strip() for p in result.stdout.split(SPLIT_MARKER)]

        if len(parts) < 6: 
            raise Exception(f"Invalid output format (got {len(parts)} parts, expected >= 6)")

        stat1 = parts[0]
        stat2 = parts[1]
        free_raw = parts[2]
        uptime_raw = parts[3]
        counts_raw = parts[4]
        ps_raw = parts[5]

        graph_data = {
            'server_name': server_name,
            'uptime': 'N/A',
            'load_avg': 'N/A',
            'tasks_info': 'Tasks: ?',
            'cpus': [],
            'ram': {'used': 0, 'total': 1, 'percent': 0},
            'swap': {'used': 0, 'total': 1, 'percent': 0},
            'processes': []
        }

        try:
            c1 = parse_proc_stat(stat1)
            c2 = parse_proc_stat(stat2)
            core_keys = [k for k in c1.keys() if k != 'cpu' and k.startswith('cpu')]
            
            core_keys.sort(key=lambda x: int(x.replace('cpu', '')) if x.replace('cpu', '').isdigit() else 999)

            for k in core_keys:
                if k not in c2: continue
                dt = c2[k]['total'] - c1[k]['total']
                di = c2[k]['idle'] - c1[k]['idle']
                usage = ((1 - (di / dt)) * 100) if dt > 0 else 0
                graph_data['cpus'].append({'id': int(k.replace('cpu','')), 'usage': usage})
        except Exception as e:
            logging.error(f"HTOP CPU parse error: {e}")

        try:
            ml = free_raw.splitlines()
            for l in ml:
                l = l.strip()
                p = l.split()
                if not p: continue

                key = p[0].replace(':', '')

                if key == 'Mem' and len(p) >= 3:
                    try:
                        t, u = int(p[1]), int(p[2])
                        graph_data['ram'] = {'used': u, 'total': t, 'percent': (u/t*100) if t>0 else 0}
                    except ValueError: pass
                if key == 'Swap' and len(p) >= 3:
                    try:
                        t, u = int(p[1]), int(p[2])
                        graph_data['swap'] = {'used': u, 'total': t, 'percent': (u/t*100) if t>0 else 0}
                    except ValueError: pass
        except Exception as e:
            logging.error(f"HTOP RAM parse error: {e}")

        try:
            
            um = re.search(r'up\s+(.*?),\s+\d+\s+user', uptime_raw)
            if um:
                graph_data['uptime'] = um.group(1).strip()
            else:
                
                um_simple = uptime_raw.split('user')[0].split('up')[-1].strip().rstrip(',')
                if um_simple: graph_data['uptime'] = um_simple

            lm = re.search(r'load average:\s+(.*)', uptime_raw)
            graph_data['load_avg'] = lm.group(1).strip() if lm else "Unknown"
        except Exception: pass

        try:
            cnt_lines = [l for l in counts_raw.splitlines() if l.strip()]
            if len(cnt_lines) >= 3:
                procs = cnt_lines[0].strip()
                thrs = cnt_lines[1].strip()
                runn = cnt_lines[2].strip()
                graph_data['tasks_info'] = f"Tasks: {procs}, {thrs} thr; {runn} running"
        except Exception: pass

        try:
            pl = ps_raw.splitlines()
            
            start_idx = 1 if pl and 'PID' in pl[0] else 0
            
            for line in pl[start_idx:]: 
                p = line.split(None, 10)
                if len(p) < 11: continue

                graph_data['processes'].append({
                    'pid': p[0], 'user': p[1], 'pri': p[2], 'ni': p[3],
                    'virt': f"{int(p[4])//1024}M" if p[4].isdigit() else p[4], 
                    'res': f"{int(p[5])//1024}M" if p[5].isdigit() else p[5],
                    's': p[6], 'pcpu': p[7], 'pmem': p[8], 'time': p[9], 'comm': p[10]
                })
        except Exception as e:
            logging.error(f"HTOP Process parse error: {e}")

        image_bytes = await asyncio.to_thread(generate_htop_image, graph_data)
        photo_file = BufferedInputFile(image_bytes.read(), filename=f"htop_{server_id}.png")
        markup = get_htop_refresh_keyboard(server_id)

        if "refresh" in action and callback.message.photo:
            media = InputMediaPhoto(media=photo_file, caption=f"📊 <b>HTOP: {server_name}</b>")
            await callback.message.edit_media(media, reply_markup=markup)
        else:
            try: await callback.message.delete()
            except: pass

            await bot.send_photo(
                chat_id=callback.message.chat.id,
                message_thread_id=callback.message.message_thread_id,
                photo=photo_file,
                caption=f"📊 <b>HTOP: {server_name}</b>",
                reply_markup=markup
            )

    except Exception as e:
        logging.error(f"HTOP Fail: {e}")
        try: 
            error_text = f"❌ <b>HTOP Error:</b> {str(e)}"
            if callback.message.photo:
                await callback.message.edit_caption(caption=error_text)
            else:
                await callback.message.edit_text(error_text)
        except: pass
