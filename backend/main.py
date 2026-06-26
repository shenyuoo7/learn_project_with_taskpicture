import json

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, IMAGES_DIR, PROFILE_PATH, REPORTS_DIR, ensure_project_dirs
from .report_generator import generate_report
from .schemas import (
    Profile,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportStartResponse,
    ReportStatusResponse,
)
from .task_manager import create_report_task, get_report_status, run_report_task


DEFAULT_PROFILE = Profile(
    my_background="我是嵌入式新手，会一点 Python，STM32 目前只完成过点亮 LED。我不熟悉硬件供电、接线、PWM、UART、嵌入式 Linux 和模型部署。",
    job_goal="我希望通过项目提升嵌入式软件、嵌入式 Linux、AIoT、工业机器人方向的求职竞争力。",
    learning_preference="我喜欢中文解释为主，专业名词保留英文缩写和英文全称。我希望先专业解释，再用新手能懂的话解释。",
    diagram_preference="图解要求直观、准确，概念图可以适度风趣幽默。",
    task_preference="我不需要学习计划，只需要由浅到深的可上手任务清单。",
)

app = FastAPI(title="计算机项目知识地图生成 Agent")


def model_to_dict(model: Profile) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.on_event("startup")
def on_startup() -> None:
    ensure_project_dirs()
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(
            json.dumps(model_to_dict(DEFAULT_PROFILE), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/profile", response_model=Profile)
def get_profile() -> Profile:
    ensure_project_dirs()
    if not PROFILE_PATH.exists():
        return DEFAULT_PROFILE
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return Profile(**data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取 profile.json 失败：{exc}") from exc


@app.post("/api/profile/save", response_model=Profile)
def save_profile(profile: Profile) -> Profile:
    ensure_project_dirs()
    PROFILE_PATH.write_text(json.dumps(model_to_dict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


@app.post("/api/report/start", response_model=ReportStartResponse)
async def report_start(request: ReportGenerateRequest, background_tasks: BackgroundTasks) -> ReportStartResponse:
    report_id, _status = create_report_task(request)
    background_tasks.add_task(run_report_task, report_id, request)
    return ReportStartResponse(report_id=report_id, status="started")


@app.get("/api/report/status/{report_id}", response_model=ReportStatusResponse)
def report_status(report_id: str) -> ReportStatusResponse:
    status = get_report_status(report_id)
    if status is None:
        raise HTTPException(status_code=404, detail="未找到对应报告任务。")
    return ReportStatusResponse(**status)


@app.post("/api/report/generate", response_model=ReportGenerateResponse)
async def report_generate(request: ReportGenerateRequest) -> ReportGenerateResponse:
    """Legacy endpoint. New UI should use /api/report/start and /api/report/status/{report_id}."""
    try:
        report_id, filename, markdown = await generate_report(request.profile, request.project)
        return ReportGenerateResponse(report_id=report_id, filename=filename, markdown=markdown)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成报告失败：{exc}") from exc


@app.get("/api/report/export/{report_id}")
def export_report(report_id: str) -> FileResponse:
    report_path = REPORTS_DIR / report_id / "report.md"
    if not report_path.exists():
        matches = sorted(REPORTS_DIR.glob(f"*{report_id}*.md"))
        if not matches:
            raise HTTPException(status_code=404, detail="未找到对应 Markdown 报告文件。")
        report_path = matches[-1]
    return FileResponse(
        report_path,
        media_type="text/markdown; charset=utf-8",
        filename=report_path.name,
    )


@app.get("/api/report/export_pdf/{report_id}")
def export_report_pdf(report_id: str) -> FileResponse:
    pdf_path = REPORTS_DIR / report_id / "report.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="未找到对应 PDF 报告文件。")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@app.get("/api/report/log/{report_id}")
def export_report_log(report_id: str) -> FileResponse:
    from .report_logger import get_log_path

    log_path = get_log_path(report_id)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="未找到对应日志文件。")
    return FileResponse(log_path, media_type="text/plain; charset=utf-8", filename=log_path.name)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
