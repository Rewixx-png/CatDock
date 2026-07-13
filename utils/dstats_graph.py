import io
from PIL import Image, ImageDraw, ImageFont
from utils.flag_manager import extract_and_clean_name, get_flag_image

SCALE = 4 

def s(val: int | float) -> int:
    return int(val * SCALE)

C_BG = "#0b1120"
C_CARD = "#1e293b"
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

def draw_mini_bar(draw, x, y, w, h, percent, color_override=None):
    track_color = "#0f172a" 
    draw_rounded_rect(draw, [x, y, x + w, y + h], radius=h//2, fill="#0f172a")
    color = C_SUCCESS
    if percent > 50: color = C_WARN
    if percent > 80: color = C_DANGER
    if color_override: color = color_override
    fill_w = int(w * (percent / 100))
    if fill_w < h and percent > 0: fill_w = h
    if fill_w > w: fill_w = w
    if fill_w > 0:
        draw_rounded_rect(draw, [x, y, x + fill_w, y + h], radius=h//2, fill=color)

def generate_dstats_image(data: list, server_name: str) -> io.BytesIO:
    MAX_ROWS = 15 
    BASE_ROW_H = 35
    BASE_HEADER_H = 100
    BASE_TABLE_HEADER_H = 30
    BASE_PADDING = 20
    BASE_W = 900
    display_data = data[:MAX_ROWS]

    W = s(BASE_W)
    ROW_H = s(BASE_ROW_H)
    HEADER_H = s(BASE_HEADER_H)
    TABLE_HEADER_H = s(BASE_TABLE_HEADER_H)
    PADDING = s(BASE_PADDING)
    H = HEADER_H + TABLE_HEADER_H + (len(display_data) * ROW_H) + PADDING * 2

    img = Image.new('RGB', (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    font_header = get_font(22, bold=True)
    font_bold = get_font(11, bold=True)
    font_mono = get_font(11)
    font_small = get_font(10)

    draw_rounded_rect(draw, [PADDING, PADDING, W-PADDING, PADDING+s(70)], radius=s(12), fill=C_CARD, outline=C_BORDER, width=s(1))

    country_code, clean_name = extract_and_clean_name(server_name)
    flag_img = get_flag_image(country_code, height=s(28))
    
    text_x = PADDING + s(20)
    if flag_img:
        img.paste(flag_img, (text_x, PADDING + s(18)), flag_img)
        text_x += flag_img.width + s(15)

    draw.text((text_x, PADDING + s(15)), f"DOCKER STATS: {clean_name}", font=font_header, fill=C_ACCENT)
    draw.text((PADDING + s(20), PADDING + s(45)), f"Active Containers: {len(data)}", font=font_bold, fill=C_TEXT_SEC)

    headers = [("CONTAINER", s(200), s(20)), ("CPU %", s(120), s(220)), ("MEM USAGE / %", s(180), s(340)), ("NET I/O", s(140), s(520)), ("BLOCK I/O", s(140), s(660)), ("PIDS", s(60), s(800))]
    table_y = PADDING + s(80)
    draw.rectangle([PADDING, table_y, W-PADDING, table_y + s(25)], fill=C_BORDER)

    for title, w, x_off in headers:
        draw.text((PADDING + x_off, table_y + s(5)), title, font=font_bold, fill=C_TEXT_MAIN)

    current_y = table_y + s(30)
    for i, row in enumerate(display_data):
        if i % 2 == 0:
            draw.rectangle([PADDING, current_y - s(2), W-PADDING, current_y + ROW_H - s(2)], fill="#162032")
        name = row['Name']
        if len(name) > 25: name = name[:23] + ".."
        color = C_TEXT_MAIN
        if "catdock" in name.lower() or "db" in name.lower(): color = C_CYAN
        draw.text((PADDING + s(20), current_y + s(8)), name, font=font_mono, fill=color)

        cpu_val_str = row['CPUPerc'].replace('%', '')
        try: cpu_val = float(cpu_val_str)
        except: cpu_val = 0.0
        draw_mini_bar(draw, PADDING + s(220), current_y + s(20), s(80), s(4), cpu_val)
        draw.text((PADDING + s(220), current_y + s(5)), row['CPUPerc'], font=font_bold, fill=C_TEXT_MAIN)

        mem_perc_str = row['MemPerc'].replace('%', '')
        try: mem_val = float(mem_perc_str)
        except: mem_val = 0.0
        draw_mini_bar(draw, PADDING + s(340), current_y + s(20), s(100), s(4), mem_val, color_override=C_PURPLE)
        mem_text = f"{row['MemUsage']} ({row['MemPerc']})"
        draw.text((PADDING + s(340), current_y + s(5)), mem_text, font=font_small, fill=C_TEXT_SEC)

        draw.text((PADDING + s(520), current_y + s(8)), row['NetIO'], font=font_mono, fill=C_TEXT_DIM)
        draw.text((PADDING + s(660), current_y + s(8)), row['BlockIO'], font=font_mono, fill=C_TEXT_DIM)
        
        pids = row['PIDs']
        pid_color = C_TEXT_DIM
        if pids.isdigit() and int(pids) > 100: pid_color = C_WARN
        draw.text((PADDING + s(800), current_y + s(8)), pids, font=font_bold, fill=pid_color)
        current_y += ROW_H

    draw.line([PADDING, current_y, W-PADDING, current_y], fill=C_BORDER, width=s(1))
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
