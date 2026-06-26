import asyncio
import hashlib
import json
import re
import shutil
import traceback
from pathlib import Path
from typing import Any, Optional

from .config import IMAGES_DIR
from .image_client import ImageClient
from .report_logger import log_event
from .schemas import ProjectInfo


AI_STYLE_SUFFIX = """

图片用途：学习报告插图。
画面风格：白底或浅色背景，扁平化漫画风 / 信息图风，简洁直观，风趣但准确。
限制：不要复杂背景，不要密集文字，中文文字尽量少，图片质量要明显高于火柴人图。
目标：图必须服务知识点理解，不能只是装饰。Generate exactly one image asset. Return only the image result.
""".strip()

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
IMAGE_RETRY_DELAYS = [3, 5, 8]
POST_IMAGE_DELAY_SECONDS = 2


DOMAIN_POINTS = {
    "hardware": ["系统模块分工", "GND 共地", "电源 VCC 与电流能力", "PWM 控制", "UART 通信", "GPIO 与信号线", "最小硬件闭环"],
    "game": ["游戏循环 Game Loop", "玩家输入 Input", "第一人称摄像机 Camera", "3D 坐标 Transform", "碰撞检测 Collider", "射线检测 Raycast", "渲染反馈 Rendering"],
    "web": ["前端与后端分工", "HTTP 请求与响应", "API 接口", "数据库模型", "鉴权 Auth", "状态保持 Session/Cookie", "部署边界"],
    "ai": ["AI API 调用", "工具调用 Function Calling", "数据输入", "模型推理 Inference", "提示词或特征工程", "评估指标", "结果解释", "隐私与偏差风险"],
    "system": ["内存 Memory", "进程与线程", "中断 Interrupt", "文件系统", "编译/链接", "AST 抽象语法树", "代码生成"],
    "crawler": ["HTTP 抓取", "HTML 解析", "反爬限制", "任务队列", "去重与存储", "速率限制"],
    "general": ["项目模块分工", "数据流", "核心处理逻辑", "最小切入口"],
}

REQUIRED_WEB_AI_POINTS = [
    "前端与后端分工",
    "HTTP 请求与响应",
    "API 接口",
    "数据库模型",
    "鉴权 Auth",
    "AI API 调用",
    "工具调用 Function Calling",
    "状态保持 Session/Cookie",
]

SLUG_ALIASES = {
    "数据输入": "data_input",
    "模型推理 inference": "model_inference",
    "模型推理": "model_inference",
    "提示词或特征工程": "prompt_feature_engineering",
    "提示词工程": "prompt_engineering",
    "特征工程": "feature_engineering",
    "评估指标": "evaluation_metrics",
    "api 集成": "api_integration",
    "结果解释": "result_explanation",
    "隐私与偏差风险": "privacy_bias_risk",
    "系统模块分工": "system_module_roles",
    "gnd 共地": "common_ground",
    "电源 vcc 与电流能力": "vcc_current_capacity",
    "pwm 控制": "pwm_control",
    "uart 通信": "uart_communication",
    "gpio 与信号线": "gpio_signal_line",
    "最小硬件闭环": "minimum_hardware_loop",
    "游戏循环 game loop": "game_loop",
    "玩家输入 input": "player_input",
    "第一人称摄像机 camera": "first_person_camera",
    "3d 坐标 transform": "transform_3d",
    "碰撞检测 collider": "collider_detection",
    "射线检测 raycast": "raycast",
    "渲染反馈 rendering": "rendering_feedback",
    "前端与后端分工": "frontend_backend_roles",
    "http 请求响应": "http_request_response",
    "http 请求与响应": "http_request_response",
    "api 接口": "api_endpoint",
    "数据库模型": "database_model",
    "鉴权 auth": "authentication",
    "状态保持 session jwt": "session_jwt_state",
    "状态保持 session cookie": "session_cookie_state",
    "ai api 调用": "ai_api_call",
    "工具调用 function calling": "function_calling",
    "部署边界": "deployment_boundary",
    "内存 memory": "memory",
    "进程与线程": "process_thread",
    "中断 interrupt": "interrupt",
    "文件系统": "file_system",
    "编译链接": "compile_link",
    "ast 抽象语法树": "ast",
    "代码生成": "code_generation",
    "http 抓取": "http_fetching",
    "html 解析": "html_parsing",
    "反爬限制": "anti_crawling",
    "任务队列": "task_queue",
    "去重与存储": "dedupe_storage",
    "速率限制": "rate_limit",
    "项目模块分工": "project_module_roles",
    "数据流": "data_flow",
    "核心处理逻辑": "core_processing_logic",
    "最小切入口": "minimum_entry",
}


def slugify(value: str) -> str:
    normalized = re.sub(r"[\s/_-]+", " ", value.strip().lower())
    normalized = normalized.replace("/", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized in SLUG_ALIASES:
        return SLUG_ALIASES[normalized]

    ascii_parts = re.findall(r"[a-z0-9]+", normalized)
    if ascii_parts:
        slug = "_".join(ascii_parts)
        return slug[:64].strip("_") or "image"

    digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:8]
    return f"image_{digest}"


def detect_domains(project: ProjectInfo) -> list[str]:
    text = " ".join(
        [
            project.project_name,
            project.project_description,
            project.project_type,
            project.target_direction,
            project.available_equipment,
            project.current_focus,
        ]
    ).lower()
    hints = {
        "hardware": ["嵌入式", "单片机", "stm32", "rv1126", "开发板", "传感器", "摄像头", "电机", "舵机", "机器人", "物联网", "uart", "pwm", "gpio", "电源", "接线"],
        "game": ["游戏", "fps", "第一人称", "射击", "3d", "unity", "unreal", "godot", "碰撞", "摄像机", "渲染"],
        "web": ["web", "网站", "前端", "后端", "数据库", "电商", "聊天", "即时通信", "小程序", "http", "登录", "api"],
        "ai": ["ai", "模型", "rag", "推荐", "简历筛选", "识别", "推理", "llm", "机器学习", "agent"],
        "system": ["操作系统", "内核", "编译器", "文件系统", "进程", "线程", "内存", "中断", "汇编", "代码生成"],
        "crawler": ["爬虫", "抓取", "反爬", "解析", "网页采集"],
    }
    domains = [domain for domain, words in hints.items() if any(word in text for word in words)]
    return domains or ["general"]


def important_points_for_project(project: ProjectInfo, mode: str) -> list[str]:
    domains = detect_domains(project)
    points: list[str] = []

    if "web" in domains or "ai" in domains:
        for point in REQUIRED_WEB_AI_POINTS:
            if point not in points:
                points.append(point)

    for domain in domains:
        for point in DOMAIN_POINTS.get(domain, DOMAIN_POINTS["general"]):
            if point not in points:
                points.append(point)

    base_limit = {"fast": 8, "standard": 12, "deep": 16}.get(mode, 12)
    required_minimum = len(REQUIRED_WEB_AI_POINTS) if ("web" in domains or "ai" in domains) else 0
    limit = max(base_limit, required_minimum)
    return points[:limit]


def _image_item(
    image_id: str,
    knowledge_point: str,
    title: str,
    purpose: str,
    image_type: str,
    importance_level: str,
    prompt: str,
    filename: str,
    target_section: str,
) -> dict[str, Any]:
    return {
        "image_id": image_id,
        "knowledge_point": knowledge_point,
        "title": title,
        "purpose": purpose,
        "image_type": image_type,
        "importance_level": importance_level,
        "prompt": prompt,
        "filename": filename,
        "target_section": target_section,
        "status": "pending",
        "error": None,
    }


def build_image_plan(project: ProjectInfo, mode: str) -> list[dict[str, Any]]:
    points = important_points_for_project(project, mode)
    plan: list[dict[str, Any]] = []
    structure_items = [
        ("project_overview", "项目全貌", "项目整体结构图", "帮助读者一眼看懂项目由哪些模块组成", "1. 项目全貌"),
        ("knowledge_overview", "知识点总览", "知识点树状图", "把核心知识点组织成一张知识树", "2. 知识点总览"),
        ("knowledge_ranking", "知识点分级", "S/A/B/C 分层路线图", "说明哪些先学、哪些后学、哪些暂时别碰", "3. 知识点分级"),
        ("minimum_entry", "最小切入口", "最小实践路径图", "说明最小切入口为什么从这里开始", "8. 最小切入口"),
    ]
    for index, (image_id, point, title, purpose, target_section) in enumerate(structure_items, start=1):
        plan.append(
            _image_item(
                image_id=image_id,
                knowledge_point=point,
                title=title,
                purpose=purpose,
                image_type="structure",
                importance_level="S",
                prompt=f"为项目《{project.project_name}》生成{title}，突出：{purpose}。",
                filename=f"fig_{index:02d}_{image_id}.png",
                target_section=target_section,
            )
        )

    start_index = len(plan) + 1
    for offset, point in enumerate(points, start=0):
        prompt = f"""主题：{project.project_name}
知识点：{point}
图名：{point} 认知插图
用途：帮助初学者理解“{point}”在该项目中的作用，突出常见误区和正确认知。
请画成一张学习报告插图，信息图 + 轻松漫画风，画面准确、简洁、直观。"""
        plan.append(
            _image_item(
                image_id=f"kp_{offset + 1:02d}_{slugify(point)}",
                knowledge_point=point,
                title=f"{point} 认知插图",
                purpose=f"解释 {point} 在项目中的作用和初学者容易误解的点",
                image_type="ai",
                importance_level="S" if offset < min(6, len(points)) else "A",
                prompt=prompt + "\n\n" + AI_STYLE_SUFFIX,
                filename=f"fig_{start_index + offset:02d}_{slugify(point)}.png",
                target_section="4. 核心知识点卡片",
            )
        )

    if mode in {"standard", "deep"} and points:
        point = points[0]
        plan.append(
            _image_item(
                image_id=f"pitfall_{slugify(point)}",
                knowledge_point=f"{point} 常见误区",
                title=f"{point} 常见误区对比图",
                purpose="用错误示范和正确认知对比，降低新手踩坑概率",
                image_type="ai",
                importance_level="A",
                prompt=f"围绕项目《{project.project_name}》中的 {point}，画一张常见误区对比图：左边是错误理解，右边是正确理解。{AI_STYLE_SUFFIX}",
                filename=f"fig_{len(plan) + 1:02d}_pitfall_{slugify(point)}.png",
                target_section="6. 常见误区",
            )
        )
    return plan


def save_image_plan(plan: list[dict[str, Any]], report_dir: Path, output_images_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    output_images_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    (report_dir / "image_plan.json").write_text(text, encoding="utf-8")
    (output_images_dir / "image_plan.json").write_text(text, encoding="utf-8")


def image_plan_to_prompt(plan: list[dict[str, Any]]) -> str:
    lines = ["图片计划 image_plan：报告中必须围绕这些图片组织图解，重要知识点卡片不能只有文字没有图。"]
    lines.append("重要：只有 status=completed 的图片允许使用 Markdown 图片引用；status=failed 的图片禁止引用 assets 路径，必须写成图片生成失败占位卡片。")
    for item in plan:
        status = item.get("status", "pending")
        if status == "completed":
            path_part = f"path=assets/{item['filename']}；允许引用"
        elif status == "failed":
            path_part = f"path=不可引用；必须插入占位卡片；失败原因={item.get('error') or '未知'}"
        else:
            path_part = f"path=assets/{item['filename']}；待生成"
        lines.append(
            f"- image_id={item['image_id']}；knowledge_point={item['knowledge_point']}；title={item['title']}；"
            f"type={item['image_type']}；level={item['importance_level']}；status={status}；filename={item['filename']}；{path_part}；"
            f"target_section={item['target_section']}；purpose={item['purpose']}"
        )
    return "\n".join(lines)


def _load_font(size: int):
    from PIL import ImageFont

    for candidate in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]:
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


def _wrapped_lines(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for char in text:
        test = line + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and line:
            lines.append(line)
            line = char
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def _draw_box(draw, box: tuple[int, int, int, int], text: str, font, fill: str, outline: str = "#111827") -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=outline, width=2)
    lines = _wrapped_lines(draw, text, font, max(80, x2 - x1 - 22))
    line_height = font.size + 6
    total_height = len(lines) * line_height
    y = y1 + max(8, ((y2 - y1) - total_height) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = x1 + ((x2 - x1) - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill="#111827")
        y += line_height


def _draw_arrow(draw, start: tuple[int, int], end: tuple[int, int], color: str = "#2563eb") -> None:
    sx, sy = start
    ex, ey = end
    draw.line((sx, sy, ex, ey), fill=color, width=5)
    if ex >= sx:
        arrow = [(ex, ey), (ex - 18, ey - 11), (ex - 18, ey + 11)]
    else:
        arrow = [(ex, ey), (ex + 18, ey - 11), (ex + 18, ey + 11)]
    draw.polygon(arrow, fill=color)


def _draw_project_overview(draw, project: ProjectInfo, font, small_font) -> None:
    boxes = {
        "user": (70, 235, 250, 330, "用户\n输入目标", "#fef3c7"),
        "frontend": (330, 165, 560, 260, "前端页面\n项目输入", "#dbeafe"),
        "backend": (650, 165, 900, 260, "FastAPI 后端\n分章生成", "#dcfce7"),
        "json": (980, 95, 1200, 190, "本地 JSON\n资料/状态", "#f3e8ff"),
        "llm": (980, 235, 1200, 330, "DeepSeek API\n章节内容生成", "#fee2e2"),
        "image": (650, 360, 900, 455, "图片 API\n核心知识点插图", "#ffedd5"),
        "export": (330, 430, 560, 525, "MD / HTML / PDF\n导出材料", "#e0f2fe"),
        "tools": (70, 430, 250, 525, "工具调用\n图像计划/日志", "#ecfccb"),
    }
    for _, (x1, y1, x2, y2, text, fill) in boxes.items():
        _draw_box(draw, (x1, y1, x2, y2), text, small_font, fill)
    _draw_arrow(draw, (250, 282), (330, 212))
    _draw_arrow(draw, (560, 212), (650, 212))
    _draw_arrow(draw, (900, 190), (980, 142), "#7c3aed")
    _draw_arrow(draw, (900, 230), (980, 282), "#dc2626")
    _draw_arrow(draw, (775, 260), (775, 360), "#ea580c")
    _draw_arrow(draw, (650, 408), (560, 478), "#0284c7")
    _draw_arrow(draw, (330, 478), (250, 478), "#65a30d")
    _draw_arrow(draw, (900, 408), (980, 330), "#ea580c")
    _draw_wrapped(draw, (70, 590), f"真实关系：{project.project_name or '项目'} 的报告不是一次性长文，而是前端提交项目目标，后端分章节调用模型、生成图片、保存本地文件并导出 PDF。", small_font, "#b91c1c", 1120)


def _draw_knowledge_tree(draw, project: ProjectInfo, font, small_font) -> None:
    groups = [
        ("Web 后端", ["前后端分工", "HTTP 请求/响应", "API 接口", "鉴权 Auth"]),
        ("AI API", ["messages 结构", "模型调用", "响应解析", "评估指标"]),
        ("数据存储", ["profile.json", "report.md", "assets 图片", "logs 日志"]),
        ("Agent 工具调用", ["image_plan", "工具调用", "任务状态", "失败重试"]),
        ("部署调试", [".venv", "本地服务", "PDF 导出", "错误排查"]),
    ]
    root = (500, 145, 780, 225)
    _draw_box(draw, root, "项目知识地图", font, "#fef9c3")
    start_x = 65
    gap = 238
    for idx, (title, leaves) in enumerate(groups):
        x = start_x + idx * gap
        top = (x, 315, x + 185, 380)
        _draw_arrow(draw, (640, 225), (x + 92, 315), "#0f766e")
        _draw_box(draw, top, title, small_font, "#e0f2fe")
        y = 420
        for leaf in leaves:
            _draw_box(draw, (x, y, x + 185, y + 52), leaf, small_font, "#f8fafc", "#64748b")
            y += 62
    _draw_wrapped(draw, (70, 680), "这张图把知识点按真实职责分层：先分清系统边界，再理解 API 调用、数据存储、工具调用和调试路径。", small_font, "#b91c1c", 1120)


def _draw_ranking(draw, project: ProjectInfo, font, small_font) -> None:
    points = important_points_for_project(project, "deep")
    levels = [
        ("S", "马上要懂", points[:4], "#fecaca"),
        ("A", "很快遇到", points[4:8], "#fde68a"),
        ("B", "知道即可", points[8:12] or ["部署边界", "评估指标", "日志排查"], "#bfdbfe"),
        ("C", "暂不深挖", ["高并发架构", "复杂权限系统", "模型微调", "云端集群部署"], "#e5e7eb"),
    ]
    y = 170
    for level, label, items, color in levels:
        draw.rounded_rectangle((80, y, 1200, y + 105), radius=18, fill=color, outline="#111827", width=2)
        draw.text((115, y + 28), f"{level} 级：{label}", font=font, fill="#111827")
        item_text = " / ".join(items[:4])
        _draw_wrapped(draw, (345, y + 25), item_text, small_font, "#111827", 800)
        y += 125
    _draw_wrapped(draw, (80, 695), "分层目标：先用 S/A 级打通最小认知闭环，B/C 级先知道边界，避免一开始掉进百科式学习。", small_font, "#b91c1c", 1120)


def _draw_minimum_entry(draw, project: ProjectInfo, font, small_font) -> None:
    steps = ["Python 脚本", "构造 messages", "HTTP POST", "DeepSeek API", "JSON 响应", "解析回复"]
    x = 70
    y = 290
    for idx, step in enumerate(steps):
        _draw_box(draw, (x, y, x + 160, y + 95), step, small_font, "#ecfdf5")
        if idx < len(steps) - 1:
            _draw_arrow(draw, (x + 160, y + 48), (x + 205, y + 48), "#0f766e")
        x += 205
    notes = [
        "最小切入口不是完整系统",
        "先验证一次模型调用能闭环",
        "再扩展前端、状态、图片、PDF",
    ]
    y2 = 480
    for note in notes:
        _draw_box(draw, (140, y2, 1140, y2 + 58), note, small_font, "#f8fafc", "#64748b")
        y2 += 72
    _draw_wrapped(draw, (70, 690), "这条路径只验证“输入 -> 模型 -> 输出”的最小闭环，适合作为 AI/Agent 项目的第一个认知入口。", small_font, "#b91c1c", 1120)


def generate_structure_image(item: dict[str, Any], project: ProjectInfo, output_path: Path) -> None:
    from PIL import Image, ImageDraw

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1280, 780), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(42)
    body_font = _load_font(27)
    small_font = _load_font(22)
    draw.rounded_rectangle((28, 28, 1252, 752), radius=22, outline="#111827", width=3, fill="#ffffff")
    draw.text((62, 58), item["title"], font=title_font, fill="#111827")
    draw.text((64, 112), project.project_name or "未命名项目", font=small_font, fill="#64748b")

    if item["image_id"] == "project_overview":
        _draw_project_overview(draw, project, body_font, small_font)
    elif item["image_id"] == "knowledge_overview":
        _draw_knowledge_tree(draw, project, body_font, small_font)
    elif item["image_id"] == "knowledge_ranking":
        _draw_ranking(draw, project, body_font, small_font)
    elif item["image_id"] == "minimum_entry":
        _draw_minimum_entry(draw, project, body_font, small_font)
    else:
        _draw_project_overview(draw, project, body_font, small_font)

    image.save(output_path)


def placeholder_card(item: dict[str, Any]) -> str:
    return f"""
> [图片生成失败：{item['title']}]
>
> - 对应知识点：{item['knowledge_point']}
> - 用途：{item['purpose']}
> - 失败原因：{item.get('error') or '未知'}
> - 建议文件名：{item['filename']}
> - 原始 prompt：{item['prompt']}
"""


def image_markdown_block(item: dict[str, Any]) -> str:
    if item.get("status") == "completed":
        return (
            f"\n这张图对应知识点 **{item['knowledge_point']}**，用于：{item['purpose']}。\n\n"
            f"![{item['title']}](assets/{item['filename']})\n\n"
            f"图注：{item['title']}。\n"
        )
    return "\n" + placeholder_card(item) + "\n"


def image_summary_block(plan: list[dict[str, Any]], report_dir: Optional[Path] = None) -> str:
    completed = [item for item in plan if item.get("status") == "completed"]
    failed = [item for item in plan if item.get("status") == "failed"]
    assets_count = 0
    if report_dir is not None and (report_dir / "assets").exists():
        assets_count = len(list((report_dir / "assets").glob("*.png")))
    rows = [
        "| 指标 | 数量 |",
        "| -- | -- |",
        f"| image_plan 总数 | {len(plan)} |",
        f"| 图片生成成功 | {len(completed)} |",
        f"| 图片生成失败 | {len(failed)} |",
        f"| report/assets 实际 PNG 数 | {assets_count} |",
    ]
    if failed:
        rows.append("")
        rows.append("| 失败图片 | 状态码 | 建议文件名 |")
        rows.append("| -- | -- | -- |")
        for item in failed:
            status_code = item.get("api_status_code") or "未知"
            rows.append(f"| {item['knowledge_point']} | {status_code} | {item['filename']} |")
    return "\n\n## 图片生成统计\n\n" + "\n".join(rows) + "\n"


def _image_failure_details(
    report_id: str,
    item: dict[str, Any],
    exc: Exception,
    output_path: Path,
    asset_path: Path,
) -> str:
    status_code = getattr(exc, "status_code", None)
    raw_response = getattr(exc, "raw_response", "") or ""
    save_path = getattr(exc, "save_path", None) or output_path
    stack = traceback.format_exc()
    return "\n".join(
        [
            "图片生成失败详情",
            f"report_id: {report_id}",
            f"image_id: {item.get('image_id')}",
            f"filename: {item.get('filename')}",
            f"knowledge_point: {item.get('knowledge_point')}",
            f"请求状态码: {status_code if status_code is not None else '未知'}",
            f"API 原始响应前 1000 字符:\n{raw_response[:1000] or '无'}",
            f"原始图片保存路径: {output_path}",
            f"报告 assets 保存路径: {asset_path}",
            f"异常声明保存路径: {save_path}",
            f"prompt:\n{item.get('prompt')}",
            f"simplified_prompt:\n{item.get('simplified_prompt') or '未使用'}",
            f"异常堆栈:\n{stack}",
        ]
    )


def _is_retryable_image_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        return True
    return status_code in RETRYABLE_STATUS_CODES


def _simplified_prompt(item: dict[str, Any], project: ProjectInfo) -> str:
    return f"""Create one clean learning-report illustration.
Project: {project.project_name}
Knowledge point: {item['knowledge_point']}
Goal: explain this concept with a simple flat infographic/comic.
Style: white background, clear boxes, simple characters or devices, very little text, no dense Chinese text, no complex background.
Must be technically accurate and easy for beginners.
Return only one image asset."""


async def _generate_ai_image_with_retries(
    report_id: str,
    client: ImageClient,
    item: dict[str, Any],
    project: ProjectInfo,
    asset_path: Path,
) -> None:
    last_exc: Optional[Exception] = None
    total_original_attempts = 1 + len(IMAGE_RETRY_DELAYS)

    for attempt_index in range(total_original_attempts):
        if asset_path.exists():
            asset_path.unlink()
        try:
            log_event(
                report_id,
                f"AI 图片生成尝试 {attempt_index + 1}/{total_original_attempts}：image_id={item['image_id']}，filename={item['filename']}",
            )
            await client.generate_image(item["prompt"], asset_path)
            log_event(report_id, f"AI 图片生成成功：image_id={item['image_id']}，attempt={attempt_index + 1}")
            return
        except Exception as exc:
            last_exc = exc
            status_code = getattr(exc, "status_code", None)
            log_event(
                report_id,
                f"AI 图片生成尝试失败：image_id={item['image_id']}，attempt={attempt_index + 1}，status_code={status_code}，error={exc}",
            )
            if attempt_index >= len(IMAGE_RETRY_DELAYS) or not _is_retryable_image_error(exc):
                break
            delay = IMAGE_RETRY_DELAYS[attempt_index]
            log_event(report_id, f"AI 图片生成将在 {delay} 秒后重试：image_id={item['image_id']}")
            await asyncio.sleep(delay)

    if asset_path.exists():
        asset_path.unlink()
    simplified = _simplified_prompt(item, project)
    item["simplified_prompt"] = simplified
    try:
        log_event(report_id, f"AI 图片生成开始简化 prompt 兜底：image_id={item['image_id']}，filename={item['filename']}")
        await client.generate_image(simplified, asset_path)
        log_event(report_id, f"AI 图片生成简化 prompt 成功：image_id={item['image_id']}")
        return
    except Exception as exc:
        last_exc = exc
        log_event(
            report_id,
            f"AI 图片生成简化 prompt 失败：image_id={item['image_id']}，status_code={getattr(exc, 'status_code', None)}，error={exc}",
        )

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"AI 图片生成失败：{item['image_id']}")


async def generate_images_from_plan(
    report_id: str,
    project: ProjectInfo,
    plan: list[dict[str, Any]],
    report_dir: Path,
) -> list[dict[str, Any]]:
    output_images_dir = IMAGES_DIR / report_id
    report_assets_dir = report_dir / "assets"
    output_images_dir.mkdir(parents=True, exist_ok=True)
    report_assets_dir.mkdir(parents=True, exist_ok=True)
    client = ImageClient()

    for item in plan:
        output_path = output_images_dir / item["filename"]
        asset_path = report_assets_dir / item["filename"]
        try:
            if item["image_type"] == "structure":
                generate_structure_image(item, project, asset_path)
            else:
                await _generate_ai_image_with_retries(report_id, client, item, project, asset_path)
            if not asset_path.exists() or asset_path.stat().st_size == 0:
                raise RuntimeError(f"图片未成功复制到报告 assets 目录：{asset_path}")
            shutil.copyfile(asset_path, output_path)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"图片未成功镜像到 outputs/images 目录：{output_path}")
            item["status"] = "completed"
            item["relative_path"] = f"assets/{item['filename']}"
            log_event(report_id, f"图片生成完成：{item['image_id']} -> assets={asset_path}；mirror={output_path}")
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            item["relative_path"] = None
            item["api_status_code"] = getattr(exc, "status_code", None)
            item["api_raw_response_preview"] = (getattr(exc, "raw_response", "") or "")[:1000]
            log_event(report_id, _image_failure_details(report_id, item, exc, output_path, asset_path))
        finally:
            await asyncio.sleep(POST_IMAGE_DELAY_SECONDS)
    save_image_plan(plan, report_dir, output_images_dir)
    return plan


def _replace_missing_image_refs(markdown: str, plan: list[dict[str, Any]], report_dir: Optional[Path]) -> str:
    if report_dir is None:
        return markdown

    for item in plan:
        filename = item["filename"]
        asset_path = report_dir / "assets" / filename
        usable = item.get("status") == "completed" and asset_path.exists()
        if usable:
            continue
        pattern = re.compile(rf"!\[[^\]]*\]\(assets/{re.escape(filename)}\)")
        if pattern.search(markdown):
            markdown = pattern.sub(placeholder_card(item).strip(), markdown)
            log_event(
                report_dir.name,
                f"已替换不存在或失败的图片引用为占位卡片：{filename}，status={item.get('status')}，asset_exists={asset_path.exists()}",
            )

    def replace_unknown(match: re.Match[str]) -> str:
        alt = match.group(1)
        rel_path = match.group(2)
        if not rel_path.startswith("assets/"):
            return match.group(0)
        target = report_dir / rel_path
        if target.exists():
            return match.group(0)
        log_event(report_dir.name, f"已替换未知缺失图片引用为占位卡片：{rel_path}")
        return (
            f"> [图片缺失：{alt}]\n"
            f">\n"
            f"> - 引用路径：{rel_path}\n"
            f"> - 失败原因：报告 assets 目录中不存在该文件。\n"
            f"> - 建议：检查 image_plan 或重新生成该图片。"
        )

    return re.sub(r"!\[([^\]]*)\]\((assets/[^)]+)\)", replace_unknown, markdown)


def append_image_blocks(markdown: str, plan: list[dict[str, Any]], report_dir: Optional[Path] = None) -> str:
    markdown = _replace_missing_image_refs(markdown, plan, report_dir)
    existing = set(re.findall(r"\]\(assets/([^)]+)\)", markdown))
    blocks = []
    if "## 图片生成统计" not in markdown:
        blocks.append(image_summary_block(plan, report_dir))
    for item in plan:
        if item.get("status") == "completed" and item["filename"] not in existing:
            blocks.append(image_markdown_block(item))
        if item.get("status") == "failed" and f"[图片生成失败：{item['title']}]" not in markdown:
            blocks.append(image_markdown_block(item))
    if not blocks:
        return markdown
    return markdown.rstrip() + "\n\n## 图解补充区\n\n" + "\n".join(blocks) + "\n"
