from pathlib import Path


FIGURES = [
    ("fig_01_pwm.png", "PWM 控制舵机示意图", "pwm"),
    ("fig_02_uart.png", "UART TX/RX/GND 接线图", "uart"),
    ("fig_03_common_ground.png", "共地与独立供电图", "gnd"),
    ("fig_04_rv1126_stm32.png", "RV1126 与 STM32 系统框图", "system"),
    ("fig_05_comic_uart.png", "UART 像两个人传纸条", "comic_uart"),
    ("fig_06_comic_pwm.png", "PWM 像节奏控制舵机", "comic_pwm"),
]


def _load_font(size: int):
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_wrapped(draw, xy, text: str, font, fill, max_width: int, line_gap: int = 8) -> int:
    x, y = xy
    line = ""
    for char in text:
        test = line + char
        bbox = draw.textbbox((x, y), test, font=font)
        if bbox[2] - bbox[0] > max_width and line:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
            line = char
        else:
            line = test
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def _base_canvas(title: str):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 720), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(40)
    draw.rectangle((24, 24, 1176, 696), outline="#111827", width=3)
    draw.text((54, 46), title, fill="#111827", font=title_font)
    draw.line((54, 104, 1146, 104), fill="#e5e7eb", width=3)
    return image, draw


def _box(draw, xy, text: str, color="#ffffff", outline="#111827", font_size=28):
    x1, y1, x2, y2 = xy
    font = _load_font(font_size)
    draw.rounded_rectangle(xy, radius=18, fill=color, outline=outline, width=3)
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y1 + (y2 - y1 - (bbox[3] - bbox[1])) / 2 - 3),
        text,
        fill="#111827",
        font=font,
    )


def _arrow(draw, start, end, fill="#111827", width=4):
    draw.line((*start, *end), fill=fill, width=width)
    x1, y1 = start
    x2, y2 = end
    if x2 >= x1:
        head = [(x2, y2), (x2 - 18, y2 - 10), (x2 - 18, y2 + 10)]
    else:
        head = [(x2, y2), (x2 + 18, y2 - 10), (x2 + 18, y2 + 10)]
    draw.polygon(head, fill=fill)


def _draw_stick_person(draw, center, label: str):
    x, y = center
    font = _load_font(22)
    draw.ellipse((x - 28, y - 80, x + 28, y - 24), outline="#111827", width=3)
    draw.line((x, y - 24, x, y + 58), fill="#111827", width=4)
    draw.line((x - 48, y + 5, x + 48, y + 5), fill="#111827", width=4)
    draw.line((x, y + 58, x - 36, y + 116), fill="#111827", width=4)
    draw.line((x, y + 58, x + 36, y + 116), fill="#111827", width=4)
    draw.text((x - 60, y + 132), label, fill="#111827", font=font)


def _figure_pwm(path: Path):
    image, draw = _base_canvas("工程准确图：PWM 控制 SG90 舵机")
    font = _load_font(26)
    red = "#c81e1e"
    draw.text((70, 130), "PWM 的关键不是“电压调小”，而是高电平持续时间和周期。", fill=red, font=font)
    y_low, y_high = 430, 240
    points = [(90, y_low), (90, y_high), (210, y_high), (210, y_low), (350, y_low), (350, y_high), (470, y_high), (470, y_low), (610, y_low), (610, y_high), (730, y_high), (730, y_low)]
    draw.line(points, fill="#111827", width=6, joint="curve")
    draw.line((90, 480, 760, 480), fill="#111827", width=3)
    draw.text((110, 205), "高电平时间", fill=red, font=font)
    draw.text((330, 516), "周期固定，占空比改变平均能量", fill="#111827", font=font)
    draw.ellipse((860, 230, 1040, 410), outline="#111827", width=5)
    draw.line((950, 320, 1038, 260), fill=red, width=7)
    draw.text((852, 448), "SG90 舵机角度响应", fill="#111827", font=font)
    image.save(path)


def _figure_uart(path: Path):
    image, draw = _base_canvas("工程准确图：UART TX/RX/GND 接线")
    font = _load_font(28)
    _box(draw, (90, 210, 360, 370), "RV1126\nTX  RX  GND", "#f8fafc")
    _box(draw, (810, 210, 1080, 370), "STM32\nRX  TX  GND", "#f8fafc")
    _arrow(draw, (360, 250), (810, 250), "#111827")
    _arrow(draw, (810, 315), (360, 315), "#111827")
    draw.line((225, 370, 225, 500, 945, 500, 945, 370), fill="#c81e1e", width=7)
    draw.text((500, 214), "TX -> RX", fill="#111827", font=font)
    draw.text((500, 344), "RX <- TX", fill="#111827", font=font)
    draw.text((408, 535), "红线：GND 共地，双方电平有共同参考点", fill="#c81e1e", font=font)
    image.save(path)


def _figure_gnd(path: Path):
    image, draw = _base_canvas("工程准确图：共地与独立供电")
    font = _load_font(26)
    _box(draw, (80, 190, 300, 320), "RV1126", "#f8fafc")
    _box(draw, (500, 190, 720, 320), "STM32", "#f8fafc")
    _box(draw, (900, 190, 1090, 320), "舵机电源", "#fff7ed")
    draw.line((190, 320, 190, 480, 610, 480, 610, 320), fill="#c81e1e", width=6)
    draw.line((610, 480, 995, 480, 995, 320), fill="#c81e1e", width=6)
    draw.text((92, 524), "GND 汇到共同参考点；不是把所有 VCC 正极乱接。", fill="#c81e1e", font=font)
    draw.text((90, 128), "独立供电可以存在，但控制信号必须有共同地。", fill="#111827", font=font)
    image.save(path)


def _figure_system(path: Path):
    image, draw = _base_canvas("工程准确图：RV1126 与 STM32 系统框图")
    font = _load_font(24)
    boxes = [
        ((70, 220, 230, 340), "摄像头"),
        ((300, 220, 500, 340), "RV1126\n目标检测"),
        ((570, 220, 760, 340), "UART\n偏移量"),
        ((830, 220, 1010, 340), "STM32\n控制算法"),
        ((1040, 440, 1160, 560), "云台\n舵机"),
    ]
    for xy, text in boxes:
        _box(draw, xy, text, "#f8fafc")
    _arrow(draw, (230, 280), (300, 280))
    _arrow(draw, (500, 280), (570, 280))
    _arrow(draw, (760, 280), (830, 280))
    _arrow(draw, (960, 340), (1085, 440), "#c81e1e")
    draw.text((70, 135), "数据链路：图像输入 -> AI 推理 -> 串口通信 -> PWM 控制 -> 云台动作", fill="#111827", font=font)
    draw.text((650, 592), "面试表达重点：讲清输入、处理、输出和调试证据。", fill="#c81e1e", font=font)
    image.save(path)


def _figure_comic_uart(path: Path):
    image, draw = _base_canvas("漫画解释图：UART 像两个人传纸条")
    font = _load_font(26)
    _draw_stick_person(draw, (220, 260), "RV1126")
    _draw_stick_person(draw, (920, 260), "STM32")
    draw.rounded_rectangle((405, 230, 790, 330), radius=18, fill="#fff7cc", outline="#111827", width=3)
    draw.text((435, 262), "纸条：目标偏左 35 像素", fill="#111827", font=font)
    _arrow(draw, (310, 285), (405, 285))
    _arrow(draw, (790, 285), (860, 285))
    draw.text((370, 452), "先约好语速：波特率一致。纸条路线：TX 接 RX。", fill="#c81e1e", font=font)
    image.save(path)


def _figure_comic_pwm(path: Path):
    image, draw = _base_canvas("漫画解释图：PWM 像节奏控制舵机")
    font = _load_font(26)
    _draw_stick_person(draw, (190, 260), "STM32")
    draw.rounded_rectangle((360, 210, 650, 330), radius=18, fill="#fff7cc", outline="#111827", width=3)
    draw.text((390, 248), "哒--哒--哒", fill="#111827", font=font)
    draw.text((390, 286), "节奏改变，角度改变", fill="#111827", font=font)
    _arrow(draw, (300, 280), (360, 280))
    draw.ellipse((840, 220, 1030, 410), outline="#111827", width=5)
    draw.line((935, 315, 1008, 260), fill="#c81e1e", width=7)
    draw.text((725, 486), "舵机听的是脉冲节奏，不是“喊大声一点”。", fill="#c81e1e", font=font)
    image.save(path)


def generate_report_images(assets_dir: Path) -> list[dict[str, str]]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    generators = {
        "pwm": _figure_pwm,
        "uart": _figure_uart,
        "gnd": _figure_gnd,
        "system": _figure_system,
        "comic_uart": _figure_comic_uart,
        "comic_pwm": _figure_comic_pwm,
    }
    generated: list[dict[str, str]] = []
    for filename, title, key in FIGURES:
        path = assets_dir / filename
        generators[key](path)
        generated.append({"filename": filename, "title": title, "path": f"assets/{filename}"})
    return generated
