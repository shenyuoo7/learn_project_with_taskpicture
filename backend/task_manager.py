import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .config import IMAGES_DIR, REPORTS_DIR, ensure_project_dirs
from .export_builder import build_report_html, build_report_pdf
from .image_plan import append_image_blocks, build_image_plan, generate_images_from_plan, save_image_plan
from .mermaid_renderer import prerender_mermaid_for_pdf
from .report_generator import build_section_plan, generate_report_sections, normalize_mode
from .report_logger import log_event
from .schemas import ReportGenerateRequest


TASKS: dict[str, dict] = {}


def _status_path(report_dir: Path) -> Path:
    return report_dir / "status.json"


def _write_status(report_dir: Path, status: dict) -> None:
    status["elapsed_seconds"] = int(time.time() - status["started_at_ts"])
    _status_path(report_dir).write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    TASKS[status["report_id"]] = status


def _public_urls(report_id: str) -> dict[str, str]:
    return {
        "markdown_url": f"/api/report/export/{report_id}",
        "pdf_url": f"/api/report/export_pdf/{report_id}",
        "html_url": f"/reports/{report_id}/report.html",
    }


def create_report_task(request: ReportGenerateRequest) -> tuple[str, dict]:
    ensure_project_dirs()
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    mode = normalize_mode(request.mode)
    total_steps = len(build_section_plan(mode, request.project)) + 7
    report_dir = REPORTS_DIR / report_id
    (report_dir / "sections").mkdir(parents=True, exist_ok=True)
    (report_dir / "assets").mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / report_id).mkdir(parents=True, exist_ok=True)

    status = {
        "report_id": report_id,
        "status": "started",
        "current_step": "已接收项目主题，等待后台任务启动",
        "progress": 1,
        "elapsed_seconds": 0,
        "total_steps": total_steps,
        "current_step_index": 0,
        "error": None,
        "failed_step": None,
        "markdown_url": None,
        "pdf_url": None,
        "html_url": None,
        "completed_steps": ["已接收项目主题"],
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "started_at_ts": time.time(),
        "mode": mode,
    }
    _write_status(report_dir, status)
    log_event(report_id, f"创建知识地图任务，模式：{mode}")
    return report_id, status


def get_report_status(report_id: str) -> Optional[dict]:
    if report_id in TASKS:
        status = TASKS[report_id]
        status["elapsed_seconds"] = int(time.time() - status["started_at_ts"])
        return status
    report_dir = REPORTS_DIR / report_id
    status_path = _status_path(report_dir)
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["elapsed_seconds"] = int(time.time() - status.get("started_at_ts", time.time()))
        TASKS[report_id] = status
        return status
    return None


async def run_report_task(report_id: str, request: ReportGenerateRequest) -> None:
    report_dir = REPORTS_DIR / report_id
    output_images_dir = IMAGES_DIR / report_id
    status = get_report_status(report_id)
    if status is None:
        return

    def update_step(step: str, progress: int, index: int) -> None:
        status["status"] = "running"
        status["current_step"] = step
        status["progress"] = max(0, min(99, progress))
        status["current_step_index"] = index
        _write_status(report_dir, status)
        log_event(report_id, f"步骤开始：{step}")

    def add_completed(step: str) -> None:
        if step not in status["completed_steps"]:
            status["completed_steps"].append(step)
        _write_status(report_dir, status)

    try:
        update_step("正在规划报告图片", 4, 1)
        mode = normalize_mode(request.mode)
        image_plan = build_image_plan(request.project, mode)
        save_image_plan(image_plan, report_dir, output_images_dir)
        add_completed(f"图片计划已生成：{len(image_plan)} 张图")
        log_event(report_id, f"image_plan 已生成，共 {len(image_plan)} 项")

        update_step("正在生成报告图片", 10, 2)
        image_plan = await generate_images_from_plan(report_id, request.project, image_plan, report_dir)
        completed_count = sum(1 for item in image_plan if item.get("status") == "completed")
        failed_count = sum(1 for item in image_plan if item.get("status") == "failed")
        add_completed(f"图片生成完成：成功 {completed_count} 张，失败 {failed_count} 张")

        update_step("正在生成知识地图大纲和正文", 18, 3)
        markdown = await generate_report_sections(
            report_id,
            request,
            report_dir,
            update_step,
            add_completed,
            image_plan=image_plan,
        )
        markdown = append_image_blocks(markdown, image_plan, report_dir)

        report_path = report_dir / "report.md"
        report_path.write_text(markdown, encoding="utf-8")
        add_completed("Markdown 知识地图已保存")
        log_event(report_id, f"Markdown 保存完成：{report_path}")

        update_step("正在预渲染 Mermaid 图表", 82, status["current_step_index"] + 1)
        pdf_markdown = prerender_mermaid_for_pdf(markdown, report_id, report_dir / "assets")
        pdf_markdown_path = report_dir / "report_pdf.md"
        pdf_markdown_path.write_text(pdf_markdown, encoding="utf-8")
        add_completed("Mermaid 预渲染处理完成")

        update_step("正在导出阅读版 HTML", 88, status["current_step_index"] + 1)
        build_report_html(report_id, report_dir, pdf_markdown)
        add_completed("HTML 知识地图已导出")

        update_step("正在导出 PDF", 94, status["current_step_index"] + 1)
        try:
            build_report_pdf(report_id, report_dir, pdf_markdown)
            add_completed("PDF 知识地图已导出")
        except Exception as exc:
            log_event(report_id, f"PDF 导出失败原因：{exc}")
            raise RuntimeError(f"PDF 导出失败：{exc}") from exc

        status["status"] = "completed"
        status["current_step"] = "项目预学习知识地图生成完成"
        status["progress"] = 100
        status.update(_public_urls(report_id))
        _write_status(report_dir, status)
        log_event(report_id, "知识地图任务完成")
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        status["failed_step"] = status.get("current_step") or "未知步骤"
        status["progress"] = max(status.get("progress", 0), 1)
        _write_status(report_dir, status)
        log_event(report_id, f"知识地图任务失败：{status['failed_step']}，{exc}")
