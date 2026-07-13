import io
from PIL import Image, ImageDraw, ImageFont
from utils.flag_manager import extract_and_clean_name, get_flag_image

SCALE = 4  

def s(val: int | float) -> int:
    return int(val * SCALE)

C_BG = "#0b1120"          
C_CARD = "#1e293b"        
C_CARD_BORDER = "#334155" 
C_BORDER = "#334155"      
C_TEXT_MAIN = "#f8fafc"   
C_TEXT_SEC = "#94a3b8"    
C_TEXT_DIM = "#475569"    
C_ACCENT = "#3b82f6"      
C_SUCCESS = "#10b981"     
C_WARN = "#f59e0b"        
C_DANGER = "#ef4444"      
C_PURPLE = "#8b5cf6"      
C_CYAN = "#06b6d4"        

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

def draw_rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def draw_modern_bar(draw, x, y, w, h, percent, label, sub_label="", color_scheme='cpu'):
    track_color = "#0f172a" 
    bar_top = y + s(18)
    bar_bottom = bar_top + h
    draw_rounded_rect(draw, [x, bar_top, x + w, bar_bottom], radius=s(4), fill=track_color)

    if color_scheme == 'cpu':
        bar_color = C_SUCCESS
        if percent > 50: bar_color = C_WARN
        if percent > 85: bar_color = C_DANGER
    elif color_scheme == 'ram':
        bar_color = C_PURPLE
    elif color_scheme == 'swap':
        bar_color = C_WARN
    else:
        bar_color = C_ACCENT

    fill_w = int(w * (percent / 100))
    if fill_w < s(4) and percent > 0: fill_w = s(4) 
    if fill_w > 0:
        draw_rounded_rect(draw, [x, bar_top, x + fill_w, bar_bottom], radius=s(4), fill=bar_color)

    font_label = get_font(10, bold=True)
    font_val = get_font(10, bold=True)
    draw.text((x, y), label.upper(), font=font_label, fill=C_TEXT_SEC)

    val_text = f"{percent:.1f}%"
    val_w = draw.textlength(val_text, font=font_val)
    draw.text((x + w - val_w, y), val_text, font=font_val, fill=C_TEXT_MAIN)

    if sub_label:
        font_sub = get_font(9)
        lbl_w = draw.textlength(label, font=font_label)
        draw.text((x + lbl_w + s(10), y + s(1)), sub_label, font=font_sub, fill=C_TEXT_DIM)

def generate_htop_image(data: dict) -> io.BytesIO:
    BASE_W, BASE_H = 800, 560
    W, H = s(BASE_W), s(BASE_H)

    img = Image.new('RGB', (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    font_header = get_font(22, bold=True)
    font_sub = get_font(11)
    font_mono = get_font(11)
    font_mono_bold = get_font(11, bold=True)
    font_mini_bold = get_font(9, bold=True)
    font_med_bold = get_font(13, bold=True)
    font_std_bold = get_font(10, bold=True)

    draw_rounded_rect(draw, [s(20), s(20), W-s(20), s(110)], radius=s(12), fill=C_CARD, outline=C_CARD_BORDER, width=s(1))

    full_name = data['server_name']
    country_code, clean_name = extract_and_clean_name(full_name)
    flag_img = get_flag_image(country_code, height=s(28))
    
    text_x = s(40)
    
    header_text_y = s(35)
    
    if flag_img:

        img.paste(flag_img, (text_x, header_text_y + s(2)), flag_img)
        text_x += flag_img.width + s(15)

    draw.text((text_x, header_text_y), clean_name, font=font_header, fill=C_ACCENT)
    draw.text((s(40), s(72)), "CATDOCK CORE MONITORING SYSTEM v5.0", font=font_sub, fill=C_TEXT_DIM)

    up_label = "UPTIME"
    up_val = data['uptime']
    draw.text((W - s(380), s(40)), up_label, font=font_mini_bold, fill=C_TEXT_SEC)
    draw.text((W - s(380), s(55)), up_val, font=font_med_bold, fill=C_SUCCESS)

    load_label = "LOAD AVERAGE"
    load_val = data['load_avg']
    draw.text((W - s(180), s(40)), load_label, font=font_mini_bold, fill=C_TEXT_SEC)
    draw.text((W - s(180), s(55)), load_val, font=font_med_bold, fill=C_TEXT_MAIN)

    tasks_info = data.get('tasks_info', 'Tasks: N/A')
    draw.text((W - s(380), s(80)), tasks_info, font=font_std_bold, fill=C_TEXT_SEC)

    current_y = s(130)

    cpu_rows_count = (len(data['cpus']) + 1) // 2
    cpu_card_h = s(40 + (cpu_rows_count * 45))
    draw_rounded_rect(draw, [s(20), current_y, W-s(20), current_y + cpu_card_h], radius=s(12), fill=C_CARD, outline=C_CARD_BORDER, width=s(1))

    col_width = s(320)
    padding_x = s(40)
    gap_x = s(60)

    for i, cpu in enumerate(data['cpus']):
        row = i // 2
        col = i % 2
        bx = padding_x + (col * (col_width + gap_x))
        by = current_y + s(25) + (row * s(45))
        draw_modern_bar(draw, bx, by, col_width, s(6), cpu['usage'], f"CORE {cpu['id']}", color_scheme='cpu')

    current_y += cpu_card_h + s(20)

    mem_card_h = s(110)
    draw_rounded_rect(draw, [s(20), current_y, W-s(20), current_y + mem_card_h], radius=s(12), fill=C_CARD, outline=C_CARD_BORDER, width=s(1))
    mem = data['ram']
    sub_ram = f"{int(mem['used'])} MB / {int(mem['total'])} MB"
    draw_modern_bar(draw, s(40), current_y + s(25), W - s(80), s(8), mem['percent'], "RAM USAGE", sub_ram, 'ram')
    swp = data['swap']
    sub_swp = f"{int(swp['used'])} MB / {int(swp['total'])} MB"
    draw_modern_bar(draw, s(40), current_y + s(65), W - s(80), s(8), swp['percent'], "SWAP AREA", sub_swp, 'swap')
    current_y += mem_card_h + s(20)

    proc_card_h = s(160)
    draw_rounded_rect(draw, [s(20), current_y, W-s(20), current_y + proc_card_h], radius=s(12), fill=C_CARD, outline=C_CARD_BORDER, width=s(1))
    headers = [("PID", s(60)), ("USER", s(100)), ("CPU%", s(60)), ("MEM%", s(60)), ("TIME", s(80)), ("COMMAND", s(300))]
    header_y = current_y + s(20)
    curr_x = s(40)
    draw.line([s(40), header_y + s(20), W-s(40), header_y + s(20)], fill=C_BORDER, width=s(1))
    for title, width in headers:
        color = C_ACCENT if "CPU" in title or "MEM" in title else C_TEXT_SEC
        draw.text((curr_x, header_y), title, font=font_std_bold, fill=color)
        curr_x += width

    row_y = header_y + s(35)
    for i, proc in enumerate(data['processes']):
        if i >= 3: break
        if i % 2 == 0: draw.rectangle([s(21), row_y - s(2), W-s(21), row_y + s(22)], fill="#162032")
        curr_x = s(40)
        draw.text((curr_x, row_y), str(proc['pid']), font=font_mono, fill=C_CYAN)
        curr_x += s(60)
        draw.text((curr_x, row_y), str(proc['user'])[:10], font=font_mono, fill=C_TEXT_MAIN)
        curr_x += s(100)
        cpu_val = float(proc['pcpu'])
        cpu_color = C_WARN if cpu_val > 50 else C_TEXT_MAIN
        draw.text((curr_x, row_y), f"{cpu_val:.1f}", font=font_mono_bold, fill=cpu_color)
        curr_x += s(60)
        draw.text((curr_x, row_y), f"{float(proc['pmem']):.1f}", font=font_mono, fill=C_TEXT_MAIN)
        curr_x += s(60)
        draw.text((curr_x, row_y), str(proc['time']), font=font_mono, fill=C_TEXT_SEC)
        curr_x += s(80)
        cmd = str(proc['comm'])
        draw.text((curr_x, row_y), cmd[:50], font=font_mono, fill=C_TEXT_MAIN)
        row_y += s(24)

    footer_text = "CATDOCK CORE MONITORING SYSTEM v5.0"
    w_ft = draw.textlength(footer_text, font=get_font(10))
    draw.text(((W - w_ft) / 2, H - s(20)), footer_text, font=get_font(10), fill=C_TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
