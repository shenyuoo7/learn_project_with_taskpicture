from pathlib import Path
from typing import Any, Callable, Optional

from .image_plan import image_plan_to_prompt
from .llm_client import DeepSeekClient
from .quality_checker import check_and_patch_report
from .report_logger import log_event
from .schemas import Profile, ProjectInfo, ReportGenerateRequest


MODE_CONFIGS = {
    "fast": {
        "label": "快速认知版",
        "target_words": "1500～2500 字",
        "section_words": "250～500 字",
        "timeout": 180,
        "temperature": 0.25,
    },
    "standard": {
        "label": "知识地图版",
        "target_words": "4000～7000 字",
        "section_words": "500～900 字",
        "timeout": 240,
        "temperature": 0.32,
    },
    "deep": {
        "label": "认知深化版",
        "target_words": "8000～12000 字",
        "section_words": "800～1300 字",
        "timeout": 300,
        "temperature": 0.35,
    },
}


DOMAIN_HINTS = {
    "hardware": ["嵌入式", "单片机", "STM32", "RV1126", "开发板", "传感器", "摄像头", "电机", "舵机", "机器人", "物联网", "IoT", "UART", "PWM", "GPIO", "PCB", "电源", "接线"],
    "game": ["游戏", "FPS", "第一人称", "射击", "3D", "Unity", "Unreal", "Godot", "碰撞", "摄像机", "渲染"],
    "web": ["Web", "网站", "前端", "后端", "数据库", "电商", "聊天", "即时通信", "小程序", "HTTP", "登录", "API"],
    "ai": ["AI", "模型", "RAG", "推荐", "简历筛选", "识别", "推理", "LLM", "机器学习", "深度学习", "Agent"],
    "system": ["操作系统", "内核", "编译器", "文件系统", "进程", "线程", "内存", "中断", "汇编", "语言处理", "代码生成"],
    "crawler": ["爬虫", "抓取", "反爬", "解析", "网页采集", "采集系统"],
}


def normalize_mode(mode: str) -> str:
    mapping = {
        "快速认知版": "fast",
        "快速测试版": "fast",
        "知识地图版": "standard",
        "标准学习版": "standard",
        "认知深化版": "deep",
        "深度报告版": "deep",
        "quick": "fast",
        "test": "fast",
        "normal": "standard",
        "full": "deep",
    }
    value = (mode or "standard").strip()
    return mapping.get(value, value if value in MODE_CONFIGS else "standard")


def combined_project_text(project: ProjectInfo) -> str:
    return " ".join(
        [
            project.project_name,
            project.project_description,
            project.project_type,
            project.target_direction,
            project.available_equipment,
            project.current_focus,
        ]
    )


def detect_domains(project: ProjectInfo) -> list[str]:
    text = combined_project_text(project).lower()
    domains = []
    for domain, hints in DOMAIN_HINTS.items():
        if any(hint.lower() in text for hint in hints):
            domains.append(domain)
    return domains or ["general"]


def is_hardware_project(project: ProjectInfo) -> bool:
    return "hardware" in detect_domains(project)


def build_section_plan(mode: str, project: Optional[ProjectInfo] = None) -> list[dict[str, str]]:
    return [
        {"title": "1. 项目全貌", "focus": "一句话解释项目是什么，识别项目领域，给出输入到输出的整体链路。"},
        {"title": "2. 知识点总览", "focus": "列出完成项目前需要建立认知的知识点，突出大白话解释、专业解释和项目作用。"},
        {"title": "3. 知识点分级", "focus": "按 S/A/B/C 过滤学习噪音，说明哪些马上懂、哪些后续学、哪些暂时别深挖。"},
        {"title": "4. 核心知识点卡片", "focus": "对 S 级和重要 A 级知识点生成认知卡片，每个重要知识点必须配图。"},
        {"title": "5. 图解", "focus": "集中说明结构图、知识图谱、分层图、机制图、类比图分别帮助理解什么。"},
        {"title": "6. 常见误区", "focus": "列出与项目强相关的新手误区，尽量用错误示范图或对比图辅助理解。"},
        {"title": "7. 自测", "focus": "给出 8～15 个上手前自测问题，用来判断认知是否建立。"},
        {"title": "8. 最小切入口", "focus": "只给最小切入口、为什么从这里开始、需要先理解的知识点，不写完整教程。"},
    ]


def profile_to_text(profile: Profile) -> str:
    return "\n".join(
        [
            f"我的基础：{profile.my_background}",
            f"求职目标：{profile.job_goal}",
            f"学习偏好：{profile.learning_preference}",
            f"图解偏好：{profile.diagram_preference}",
            f"任务偏好：{profile.task_preference}",
        ]
    )


def project_to_text(project: ProjectInfo) -> str:
    return "\n".join(
        [
            f"项目名称：{project.project_name}",
            f"项目描述：{project.project_description}",
            f"项目类型：{project.project_type}",
            f"目标方向：{project.target_direction}",
            f"已有设备 / 环境：{project.available_equipment}",
            f"当前关注点：{project.current_focus}",
        ]
    )


def build_outline_markdown(project: ProjectInfo, mode: str, plan: list[dict[str, str]]) -> str:
    config = MODE_CONFIGS[mode]
    domains = "、".join(detect_domains(project))
    lines = [
        "# 项目预学习知识地图大纲",
        "",
        f"- 输出模式：{config['label']}",
        f"- 目标长度：{config['target_words']}",
        f"- 项目名称：{project.project_name}",
        f"- 自动识别领域：{domains}",
        "",
        "## 章节计划",
    ]
    for index, section in enumerate(plan, start=1):
        lines.append(f"{index}. {section['title']}：{section['focus']}")
    return "\n".join(lines) + "\n"


def build_front_matter(project: ProjectInfo, mode: str, plan: list[dict[str, str]]) -> str:
    config = MODE_CONFIGS[mode]
    toc = "\n".join([f"- {section['title']}" for section in plan])
    return f"""# 项目预学习知识地图

> 输出模式：{config["label"]}  
> 目标长度：{config["target_words"]}  
> 项目名称：{project.project_name or "未命名项目"}

[重点] 这份文档的目标是帮你在动手前建立项目认知，扫清知识盲区；它不是完整项目教程、代码生成器或安装环境说明书。

## 目录

{toc}

"""


def output_mode_rules(mode: str) -> str:
    if mode == "fast":
        return """快速认知版：1500～2500 字。只保留项目全貌、核心知识点、S/A/B/C 分级、少量核心认知卡片、3～5 张图解建议、自测和最小切入口。"""
    if mode == "deep":
        return """认知深化版：8000～12000 字。关键知识点解释更透，补充概念对比、典型误区、因果关系、术语表和后续深入方向，但仍不能写成完整教程。"""
    return """知识地图版：4000～7000 字。完整模块拆解、完整知识点地图、S/A/B/C 分级、认知卡片、依赖关系、盲区、图解清单、误区、自测和最小切入口。"""


def domain_blind_spot_rules(project: ProjectInfo) -> str:
    domains = detect_domains(project)
    rules = []
    if "hardware" in domains:
        rules.append("项目涉及硬件：必须补充 VCC、GND/共地、信号线、电压等级、电流能力、独立供电、GPIO、PWM、UART/I2C/SPI、执行器、引脚、原理图、万用表/示波器/逻辑分析仪等盲区。")
    else:
        rules.append("项目不涉及明显硬件时，硬件盲区部分写：本项目不涉及明显硬件部分，本章略。")
    if "game" in domains:
        rules.append("项目涉及游戏：必须补充游戏引擎、3D 坐标、玩家输入、摄像机、碰撞检测、Raycast、渲染反馈、UI 等认知盲区。")
    if "web" in domains:
        rules.append("项目涉及 Web：必须补充前端、后端、数据库、HTTP、鉴权、状态保持、部署边界等认知盲区。")
    if "ai" in domains:
        rules.append("项目涉及 AI：必须补充数据、模型、推理、评估、API/部署、输入输出质量等认知盲区。")
    if "system" in domains:
        rules.append("项目涉及系统底层：必须补充内存、进程、线程、中断、文件系统、网络、编译/链接或代码生成等认知盲区。")
    return "\n".join(f"- {rule}" for rule in rules)


def build_section_prompt(
    request: ReportGenerateRequest,
    mode: str,
    section_index: int,
    total_sections: int,
    section: dict[str, str],
    outline: str,
    previous_summary: str,
    image_plan: list[dict[str, Any]],
) -> str:
    config = MODE_CONFIGS[mode]
    return f"""请生成“项目预学习知识地图”的一个章节。

你的身份：
你是“计算机项目知识地图生成 Agent”。你不是完整项目教程作者，不是代码生成器，不是安装环境说明书。你的任务是在用户动手前快速建立项目认知，扫清知识盲区。

输出模式：{config["label"]}
整份报告目标长度：{config["target_words"]}
本章节建议长度：{config["section_words"]}
当前章节：第 {section_index}/{total_sections} 章：{section["title"]}
章节重点：{section["focus"]}

个人基础：
{profile_to_text(request.profile)}

项目信息：
{project_to_text(request.project)}

报告大纲：
{outline}

前文摘要：
{previous_summary or "暂无"}

{image_plan_to_prompt(image_plan)}

领域盲区规则：
{domain_blind_spot_rules(request.project)}

输出模式规则：
{output_mode_rules(mode)}

全局写作要求：
1. 输出 Markdown，不要输出 JSON。
2. 当前章节标题必须从 `## {section["title"]}` 开始。
3. 少写空泛背景，少写长篇废话；多用表格、清单、知识卡片。
4. 不能写成完整项目教程，不要给手把手安装步骤，不要生成完整代码。
5. 每个知识点必须先大白话解释，再专业解释，并说明在本项目中的作用。
6. 必须说明“现在掌握到什么程度就够”和“暂时不用深挖什么”。
7. S 级知识点控制在 5～10 个，A 级控制在 5～12 个；不要把所有东西都标成必须掌握。
8. 核心知识点卡片中的每个重要知识点都必须有图文位置：status=completed 的图片才可以引用，格式如：`![图名](assets/文件名.png)`。
9. 每张图前后必须有一句简短说明，解释这张图对应哪个知识点。
10. 如果图片计划里某张图 status=failed，禁止引用 assets 路径，必须在对应位置保留图片生成失败占位说明，不要让知识点只有文字。
10.1 第 4 章“核心知识点卡片”必须覆盖 image_plan 中所有 image_type=ai 的 knowledge_point；不要把重要知识点新增成纯文字卡片。
11. 不要主动输出 Mermaid 代码块；图解优先引用 image_plan 生成的 PNG 图片，必要时用 Markdown 表格或 ASCII 短框图辅助。
12. 最终 PDF 中不允许出现 `flowchart LR`、`sequenceDiagram` 或 `[图表渲染失败]` 这类 Mermaid 源码/失败文本。
13. 必须适当使用提示框标记：
    - [重点] 必须掌握内容
    - [常见坑] 新手误区或风险
    - [任务] 最小切入口或认知自测任务
    - [项目作用] 知识点在项目里的作用
"""


def fallback_readability_patch(markdown: str) -> str:
    additions = []
    if "[重点]" not in markdown:
        additions.append("[重点] 先建立项目输入、处理、输出、模块分工和知识点优先级，不要一开始就钻进完整实现细节。")
    if "[常见坑]" not in markdown:
        additions.append("[常见坑] 新手最容易把项目理解成“堆技术名词”，但真正需要先看清模块之间的输入输出关系。")
    if "[任务]" not in markdown:
        additions.append("[任务] 动手前先用一句话说清项目是什么，再画出输入到输出的流程图。")
    if "[项目作用]" not in markdown:
        additions.append("[项目作用] 知识地图的作用是帮你判断哪些先学、哪些后学、哪些暂时别碰。")
    if not additions:
        return markdown
    return markdown.rstrip() + "\n\n## 认知提示补充\n\n" + "\n\n".join(additions) + "\n"


async def generate_report_sections(
    report_id: str,
    request: ReportGenerateRequest,
    report_dir: Path,
    update_step: Callable[[str, int, int], None],
    add_completed: Callable[[str], None],
    image_plan: Optional[list[dict[str, Any]]] = None,
) -> str:
    mode = normalize_mode(request.mode)
    config = MODE_CONFIGS[mode]
    plan = build_section_plan(mode, request.project)
    sections_dir = report_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    image_plan = image_plan or []

    outline = build_outline_markdown(request.project, mode, plan)
    (report_dir / "outline.md").write_text(outline, encoding="utf-8")
    add_completed("已生成知识地图大纲")
    log_event(report_id, f"知识地图大纲已保存：{report_dir / 'outline.md'}")

    client = DeepSeekClient()
    generated_sections: list[str] = []
    previous_summary = ""

    for index, section in enumerate(plan, start=1):
        current = f"正在生成第 {index}/{len(plan)} 章：{section['title']}"
        progress = 10 + int(index / max(len(plan), 1) * 58)
        update_step(current, progress, index)
        prompt = build_section_prompt(request, mode, index, len(plan), section, outline, previous_summary, image_plan)

        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                log_event(report_id, f"开始生成章节 {index}，尝试 {attempt}/3：{section['title']}")
                content = await client.chat(
                    "你是计算机项目知识地图生成 Agent，请输出结构清晰、适合 Markdown/PDF 的项目预学习知识地图。",
                    prompt,
                    temperature=config["temperature"],
                    timeout_seconds=config["timeout"],
                )
                if not content.strip():
                    raise RuntimeError("模型返回空内容")
                section_path = sections_dir / f"section_{index:02d}.md"
                section_path.write_text(content.strip() + "\n", encoding="utf-8")
                generated_sections.append(content.strip())
                previous_summary = "\n\n".join(generated_sections[-2:])[:3200]
                add_completed(f"第 {index}/{len(plan)} 章完成：{section['title']}")
                log_event(report_id, f"章节 {index} 生成完成：{section_path}")
                break
            except Exception as exc:
                last_error = exc
                log_event(report_id, f"章节 {index} 生成失败，尝试 {attempt}/3：{exc}")
                if attempt == 3:
                    raise RuntimeError(f"第 {index} 章《{section['title']}》生成失败：{last_error}") from exc

    report = build_front_matter(request.project, mode, plan)
    report += "\n\n".join(generated_sections)
    report = fallback_readability_patch(report)
    report = check_and_patch_report(report)
    return report


async def generate_report(profile: Profile, project: ProjectInfo) -> tuple[str, str, str]:
    """Legacy synchronous API support for the old /api/report/generate endpoint."""
    from datetime import datetime
    from uuid import uuid4

    from .config import REPORTS_DIR, ensure_project_dirs

    ensure_project_dirs()
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    report_dir = REPORTS_DIR / report_id
    report_dir.mkdir(parents=True, exist_ok=True)
    request = ReportGenerateRequest(profile=profile, project=project, mode="standard")

    def noop_update(_: str, __: int, ___: int) -> None:
        return None

    def noop_completed(_: str) -> None:
        return None

    markdown = await generate_report_sections(report_id, request, report_dir, noop_update, noop_completed)
    report_path = report_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    return report_id, "report.md", markdown
