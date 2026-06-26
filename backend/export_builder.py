import html
import re
from pathlib import Path

from .report_logger import log_event


CALLOUTS = {
    "重点": ("must", "必须掌握"),
    "常见坑": ("warn", "常见坑"),
    "任务": ("task", "最小实践任务"),
    "项目作用": ("info", "项目作用"),
}


def preprocess_callouts(markdown: str) -> str:
    markdown = re.sub(r"^>\s*\[!(CAUTION|WARNING|NOTE|TIP|IMPORTANT)\]\s*$", "", markdown, flags=re.MULTILINE)

    def replace(match: re.Match) -> str:
        key = match.group(1)
        content = match.group(2).strip()
        css_class, label = CALLOUTS[key]
        return f'\n<div class="callout {css_class}"><strong>{label}</strong><p>{html.escape(content)}</p></div>\n'

    return re.sub(r"^\[(重点|常见坑|任务|项目作用)\]\s*(.+)$", replace, markdown, flags=re.MULTILINE)


def markdown_to_html(markdown: str) -> str:
    processed = preprocess_callouts(markdown)
    try:
        import markdown as markdown_lib

        return markdown_lib.markdown(
            processed,
            extensions=["tables", "fenced_code", "sane_lists"],
            output_format="html5",
        )
    except Exception:
        return "<pre>" + html.escape(processed) + "</pre>"


def build_report_html(report_id: str, report_dir: Path, markdown: str) -> Path:
    body = markdown_to_html(markdown)
    html_path = report_dir / "report.html"
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>项目预学习知识地图</title>
  <style>
    @page {{
      size: A4;
      margin: 18mm 16mm 18mm 16mm;
      @bottom-center {{ content: "第 " counter(page) " 页"; color: #64748b; font-size: 10pt; }}
    }}
    body {{
      margin: 0;
      color: #1f2937;
      font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif;
      line-height: 1.72;
      background: #fff;
    }}
    .page {{
      max-width: 980px;
      margin: 0 auto;
      padding: 28px;
    }}
    h1 {{
      font-size: 30px;
      border-bottom: 2px solid #111827;
      padding-bottom: 14px;
    }}
    h2 {{
      margin-top: 32px;
      padding-left: 12px;
      border-left: 5px solid #0f766e;
      font-size: 22px;
    }}
    h3 {{ margin-top: 24px; font-size: 18px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 8px 10px;
      vertical-align: top;
    }}
    th {{ background: #e8f3f1; }}
    pre {{
      padding: 12px;
      border: 1px solid #d8dee2;
      border-radius: 6px;
      background: #f8fafc;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    img, svg, canvas {{
      display: block;
      max-width: 100%;
      height: auto;
      margin: 12px auto;
      page-break-inside: avoid;
    }}
    blockquote {{
      margin: 14px 0;
      padding: 12px 14px;
      border-left: 5px solid #94a3b8;
      background: #f8fafc;
    }}
    .callout {{
      margin: 14px 0;
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      page-break-inside: avoid;
    }}
    .callout strong {{ display: block; margin-bottom: 5px; }}
    .callout p {{ margin: 0; }}
    .callout.must {{ border-left: 6px solid #dc2626; background: #fff1f2; }}
    .callout.warn {{ border-left: 6px solid #d97706; background: #fffbeb; }}
    .callout.task {{ border-left: 6px solid #16a34a; background: #f0fdf4; }}
    .callout.info {{ border-left: 6px solid #2563eb; background: #eff6ff; }}
    .caption {{
      color: #64748b;
      font-size: 13px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <main class="page">
    {body}
  </main>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    log_event(report_id, f"HTML 导出完成：{html_path}")
    return html_path


def _register_pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    for candidate in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\NotoSansCJK-Regular.ttc",
    ]:
        try:
            pdfmetrics.registerFont(TTFont("CNFont", candidate))
            return "CNFont"
        except Exception:
            continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        pass
    return "Helvetica"


def _normalize_pdf_text(text: str) -> str:
    replacements = {
        "⚠️": "注意：",
        "⚠": "注意：",
        "✅": "完成：",
        "❌": "失败：",
        "⏳": "进行中：",
        "⬜": "等待：",
        "📌": "提示：",
        "🔥": "重点：",
        "💡": "提示：",
        "👉": "指向：",
        "➡️": "->",
        "➡": "->",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("\ufe0f", "").replace("\u200d", "")
    return re.sub(r"[\U0001F300-\U0001FAFF]", "", text)


def _clean_inline(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "").replace("`", "")
    return html.escape(_normalize_pdf_text(cleaned))


def build_report_pdf(report_id: str, report_dir: Path, markdown: str) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        KeepTogether,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    pdf_path = report_dir / "report.pdf"
    font_name = _register_pdf_font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CNBody", fontName=font_name, fontSize=10.5, leading=17, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CNH1", fontName=font_name, fontSize=22, leading=28, spaceAfter=12))
    styles.add(ParagraphStyle(name="CNH2", fontName=font_name, fontSize=16, leading=22, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#0f766e")))
    styles.add(ParagraphStyle(name="CNH3", fontName=font_name, fontSize=13, leading=18, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="CNCode", fontName=font_name, fontSize=8.5, leading=12))
    styles.add(ParagraphStyle(name="Caption", fontName=font_name, fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#64748b")))

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 9)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(16 * mm, 285 * mm, "项目预学习知识地图")
        canvas.drawRightString(194 * mm, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    story = []
    lines = markdown.splitlines()
    i = 0
    in_code = False
    code_lines: list[str] = []

    def flush_code():
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["CNCode"]))
            story.append(Spacer(1, 6))
            code_lines.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            if in_code:
                in_code = False
                flush_code()
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        callout_match = re.match(r"\[(重点|常见坑|任务|项目作用)\]\s*(.+)", line)
        obsidian_callout_match = re.match(r">\s*\[!(CAUTION|WARNING|NOTE|TIP|IMPORTANT)\]", line)

        if not line:
            story.append(Spacer(1, 5))
        elif obsidian_callout_match:
            pass
        elif line.startswith("# "):
            story.append(Paragraph(_clean_inline(line[2:]), styles["CNH1"]))
        elif line.startswith("## "):
            story.append(Paragraph(_clean_inline(line[3:]), styles["CNH2"]))
        elif line.startswith("### "):
            story.append(Paragraph(_clean_inline(line[4:]), styles["CNH3"]))
        elif image_match:
            alt, rel = image_match.groups()
            image_path = (report_dir / rel).resolve()
            if image_path.exists():
                img = Image(str(image_path))
                max_width = 170 * mm
                max_height = 105 * mm
                scale = min(max_width / img.imageWidth, max_height / img.imageHeight, 1)
                img.drawWidth = img.imageWidth * scale
                img.drawHeight = img.imageHeight * scale
                story.append(KeepTogether([img, Paragraph(_clean_inline(alt), styles["Caption"])]))
            else:
                story.append(Paragraph(f"[图片缺失：{_clean_inline(alt)}]", styles["CNBody"]))
        elif callout_match:
            key, content = callout_match.groups()
            css_class, label = CALLOUTS[key]
            colors_by_type = {
                "must": colors.HexColor("#fff1f2"),
                "warn": colors.HexColor("#fffbeb"),
                "task": colors.HexColor("#f0fdf4"),
                "info": colors.HexColor("#eff6ff"),
            }
            table = Table(
                [[Paragraph(f"<b>{label}</b><br/>{_clean_inline(content)}", styles["CNBody"])]],
                colWidths=[170 * mm],
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors_by_type[css_class]),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6))
        elif "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[i + 1]):
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i].strip())
                i += 1
            rows = []
            for row in table_lines[0:1] + table_lines[2:]:
                cells = [Paragraph(_clean_inline(cell.strip()), styles["CNBody"]) for cell in row.strip("|").split("|")]
                rows.append(cells)
            if rows:
                col_width = 170 * mm / max(len(rows[0]), 1)
                table = Table(rows, colWidths=[col_width] * len(rows[0]), repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f3f1")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTNAME", (0, 0), (-1, -1), font_name),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 7))
            continue
        elif line.startswith(">"):
            story.append(Paragraph(_clean_inline(line.lstrip("> ")), styles["CNBody"]))
        else:
            story.append(Paragraph(_clean_inline(line), styles["CNBody"]))
        i += 1

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    log_event(report_id, f"PDF 导出完成：{pdf_path}")
    return pdf_path
