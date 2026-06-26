import re
import shutil
import subprocess
from pathlib import Path

from .report_logger import log_event


MERMAID_BLOCK_RE = re.compile(r"```mermaid\s+(.*?)```", re.DOTALL | re.IGNORECASE)


def _sanitize_mermaid(source: str) -> str:
    lines = []
    for line in source.strip().splitlines():
        safe = line.replace("{", "").replace("}", "").replace("`", "'")
        safe = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\([^)]*\)", "函数调用", safe)
        safe = re.sub(r"\[([^\]]{42,})\]", lambda m: "[" + m.group(1)[:40] + "...]", safe)
        safe = re.sub(r"\(([^)]{42,})\)", lambda m: "(" + m.group(1)[:40] + "...)", safe)
        safe = re.sub(r"\|([^|]{34,})\|", lambda m: "|" + m.group(1)[:32] + "...|", safe)
        lines.append(safe)
    return "\n".join(lines)


def _load_font(size: int):
    from PIL import ImageFont

    for candidate in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_wrapped(draw, xy, text: str, font, fill, max_width: int, line_gap: int = 8) -> None:
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


def _create_static_mermaid_placeholder(png_path: Path, title: str, reason: str) -> None:
    from PIL import Image, ImageDraw

    png_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(40)
    body_font = _load_font(26)
    small_font = _load_font(22)

    draw.rounded_rectangle((28, 28, 1172, 592), radius=22, outline="#111827", width=3, fill="#f8fafc")
    draw.text((70, 64), title, font=title_font, fill="#111827")
    draw.rounded_rectangle((90, 170, 1110, 275), radius=18, outline="#2563eb", width=2, fill="#dbeafe")
    _draw_wrapped(draw, (125, 202), "这张 Mermaid 图已转为静态 PNG，避免 PDF 中出现源码或渲染失败文本。", body_font, "#111827", 920)
    draw.rounded_rectangle((90, 330, 1110, 450), radius=18, outline="#f59e0b", width=2, fill="#fffbeb")
    _draw_wrapped(draw, (125, 360), f"原因：{reason}", small_font, "#92400e", 900)
    draw.text((90, 520), "建议：优先使用项目自动生成的结构图、知识树和路径图理解核心关系。", font=small_font, fill="#64748b")
    image.save(png_path)


def prerender_mermaid_for_pdf(markdown: str, report_id: str, assets_dir: Path) -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    mmdc = shutil.which("mmdc")
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        title = f"图表 {counter:02d}"
        source = _sanitize_mermaid(match.group(1))
        png_path = assets_dir / f"mermaid_{counter:02d}.png"
        if not mmdc:
            log_event(report_id, f"Mermaid 渲染跳过：未找到 mermaid-cli(mmdc)，{title}")
            _create_static_mermaid_placeholder(png_path, title, "未找到 mermaid-cli(mmdc)")
            return f"\n\n![{title} 静态图](assets/{png_path.name})\n\n"

        mmd_path = assets_dir / f"mermaid_{counter:02d}.mmd"
        mmd_path.write_text(source, encoding="utf-8")
        try:
            subprocess.run(
                [mmdc, "-i", str(mmd_path), "-o", str(png_path), "-b", "transparent"],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
            log_event(report_id, f"Mermaid 渲染完成：{png_path.name}")
            return f"\n\n![{title}](assets/{png_path.name})\n\n"
        except Exception as exc:
            log_event(report_id, f"Mermaid 渲染失败：{title}，{exc}")
            _create_static_mermaid_placeholder(png_path, title, f"Mermaid 渲染异常：{exc}")
            return f"\n\n![{title} 静态图](assets/{png_path.name})\n\n"

    return MERMAID_BLOCK_RE.sub(replace, markdown)
