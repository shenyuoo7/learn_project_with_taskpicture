REQUIRED_MARKERS = [
    ("1. 项目全貌", "项目全貌"),
    ("2. 知识点总览", "知识点总览"),
    ("3. 知识点分级", "知识点分级"),
    ("4. 核心知识点卡片", "核心知识点卡片"),
    ("5. 图解", "图解"),
    ("6. 常见误区", "常见误区"),
    ("7. 自测", "自测"),
    ("8. 最小切入口", "最小切入口"),
    ("S", "S/A/B/C 分级"),
    ("大白话", "大白话解释"),
    ("专业解释", "专业解释"),
    ("现在掌握到什么程度", "掌握边界"),
    ("暂时不用深挖", "暂时不用深挖"),
    ("[重点]", "重点提示框"),
    ("[常见坑]", "常见坑提示框"),
    ("[任务]", "任务提示框"),
    ("[项目作用]", "项目作用提示框"),
]


def check_and_patch_report(markdown: str) -> str:
    missing = [label for marker, label in REQUIRED_MARKERS if marker not in markdown]
    if not missing:
        return markdown

    lines = ["", "## 知识地图补充完善区", ""]
    lines.append("以下内容由基础质量检查补充，用于提醒后续生成或人工复核时需要补齐：")
    for label in missing:
        lines.append(f"- {label}：本项应服务于“动手前建立项目认知，扫清知识盲区”，不要写成完整教程。")

    if "重点提示框" in missing:
        lines.append("[重点] 开始动手前，先确认自己能说清项目全貌、知识点优先级和最小切入口。")
    if "常见坑提示框" in missing:
        lines.append("[常见坑] 不要一上来查完整教程或抄代码；先画出项目链路和知识依赖，否则很容易越学越散。")
    if "任务提示框" in missing:
        lines.append("[任务] 用 3 句话回答：这个项目是什么、由哪些模块组成、最小切入口是什么。")
    if "项目作用提示框" in missing:
        lines.append("[项目作用] 知识地图帮助你判断哪些知识现在必须懂，哪些后续再学，哪些暂时不要深挖。")
    return markdown.rstrip() + "\n\n" + "\n".join(lines) + "\n"
