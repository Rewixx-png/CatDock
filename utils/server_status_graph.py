import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from utils import bot_state
from utils.flag_manager import extract_and_clean_name, get_flag_image

SCALE = 2

C_BG = "#0b1120"
C_CARD_BG = "#1e293b"
C_CARD_BORDER = "#334155"
C_TEXT_MAIN = "#f8fafc"
C_TEXT_SEC = "#94a3b8"
C_TEXT_DIM = "#475569"

C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_ORANGE = "#f59e0b"
C_BLUE = "#3b82f6"
C_PURPLE = "#a855f7"
C_CYAN = "#06b6d4"

def s(val: int) -> int:
    return int(val * SCALE)

def get_font(size=12, bold=False):
    size = s(size)
    font_names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "arial.ttf"
    ]
    for path in font_names:
        try: return ImageFont.truetype(path, size)
        except OSError: continue
    return ImageFont.load_default()

def draw_progress_bar(draw, x, y, w, h, percent, color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=s(2), fill="#0f172a")

    fill_w = int(w * (percent / 100))
    if fill_w < s(2) and percent > 0: fill_w = s(2)
    if fill_w > w: fill_w = w

    if fill_w > 0:
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=s(2), fill=color)

def parse_percent(val_str):
    try:
        return float(val_str.replace('%', ''))
    except:
        return 0.0

def generate_server_status_image(statuses: list) -> io.BytesIO:
    PADDING = s(30)
    CARD_H = s(140)
    CARD_GAP = s(20)
    HEADER_H = s(100)

    COLS = 2
    ROWS = (len(statuses) + COLS - 1) // COLS

    W = s(1200)
    H = HEADER_H + (ROWS * CARD_H) + ((ROWS - 1) * CARD_GAP) + PADDING * 2

    img = Image.new('RGB', (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    font_header = get_font(28, bold=True)
    font_time = get_font(14)
    font_card_title = get_font(16, bold=True)
    font_card_sub = get_font(12)
    font_mono = get_font(11)
    font_bold = get_font(11, bold=True)

    draw.text((PADDING, PADDING), "📊 SERVER STATUS REPORT", font=font_header, fill=C_TEXT_MAIN)

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    draw.text((PADDING, PADDING + s(40)), f"🕒 {now_str} • CATDOCK CORE", font=font_time, fill=C_TEXT_SEC)

    start_y = HEADER_H + PADDING
    col_width = (W - (PADDING * 2) - (CARD_GAP * (COLS - 1))) // COLS

    for i, server in enumerate(statuses):
        row = i // COLS
        col = i % COLS

        x = PADDING + (col * (col_width + CARD_GAP))
        y = start_y + (row * (CARD_H + CARD_GAP))

        is_active = bot_state.server_states.get(server['id'], True)
        is_online = server['status'] == 'online'

        card_border = C_CARD_BORDER
        status_color = C_TEXT_DIM

        if not is_active:
            status_color = C_ORANGE
            card_border = C_ORANGE
            state_text = "DISABLED"
        elif not is_online:
            status_color = C_RED
            card_border = C_RED
            state_text = "OFFLINE"
        else:
            status_color = C_GREEN
            state_text = "ONLINE"

        draw.rounded_rectangle([x, y, x + col_width, y + CARD_H], radius=s(12), fill=C_CARD_BG, outline=card_border, width=s(2))

        dot_r = s(5)
        draw.ellipse([x + s(20), y + s(25) - dot_r, x + s(20) + dot_r*2, y + s(25) + dot_r], fill=status_color)

        country_code, clean_name = extract_and_clean_name(server['name'])

        name_text = f"{clean_name} ({server.get('ping', '?')}ms)"
        if not is_active: name_text += " [OFF]"

        flag_img = get_flag_image(country_code, height=s(20))
        text_x_offset = s(40)

        if flag_img:
            img.paste(flag_img, (x + s(40), y + s(14)), flag_img)
            text_x_offset += flag_img.width + s(10)

        draw.text((x + text_x_offset, y + s(15)), name_text, font=font_card_title, fill=C_TEXT_MAIN)

        content_y = y + s(50)

        if is_online and is_active:
            cpu_val = parse_percent(server['cpu'])
            draw.text((x + s(20), content_y), "CPU", font=font_bold, fill=C_TEXT_SEC)
            draw_progress_bar(draw, x + s(60), content_y + s(3), s(100), s(8), cpu_val, C_RED if cpu_val > 80 else C_BLUE)
            draw.text((x + s(170), content_y), f"{server['cpu']}", font=font_mono, fill=C_TEXT_MAIN)

            ram_val = parse_percent(server['ram'])
            ram_x_offset = s(260)
            draw.text((x + ram_x_offset, content_y), "RAM", font=font_bold, fill=C_TEXT_SEC)
            draw_progress_bar(draw, x + ram_x_offset + s(40), content_y + s(3), s(100), s(8), ram_val, C_PURPLE)
            draw.text((x + ram_x_offset + s(150), content_y), f"{server['ram']}", font=font_mono, fill=C_TEXT_MAIN)

            content_y += s(25)

            disk_val = parse_percent(server['disk'])
            draw.text((x + s(20), content_y), "DISK", font=font_bold, fill=C_TEXT_SEC)
            draw_progress_bar(draw, x + s(60), content_y + s(3), s(100), s(8), disk_val, C_CYAN)
            draw.text((x + s(170), content_y), f"{server['disk']}", font=font_mono, fill=C_TEXT_MAIN)

            net_status = "🌐 OK" if server.get('net') else "🌐 FAIL"
            net_color = C_GREEN if server.get('net') else C_RED
            draw.text((x + ram_x_offset, content_y), net_status, font=font_bold, fill=net_color)

            content_y += s(30)
            draw.line([x + s(20), content_y - s(5), x + col_width - s(20), content_y - s(5)], fill=C_CARD_BORDER, width=s(1))

            top_load = server.get('top_load', 'N/A')
            draw.text((x + s(20), content_y), f"Top Load: {top_load}", font=font_mono, fill=C_TEXT_DIM)

        else:
            draw.text((x + s(20), content_y), f"STATUS: {state_text}", font=font_bold, fill=status_color)
            if not is_active:
                ping_txt = f"Last Ping: {server.get('ping', 'N/A')}"
                draw.text((x + s(20), content_y + s(25)), ping_txt, font=font_mono, fill=C_TEXT_DIM)
            else:
                draw.text((x + s(20), content_y + s(25)), "Connection refused / Timeout", font=font_mono, fill=C_TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
