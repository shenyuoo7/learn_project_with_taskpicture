from typing import Optional

from pydantic import BaseModel, Field


class Profile(BaseModel):
    my_background: str = Field(default="")
    job_goal: str = Field(default="")
    learning_preference: str = Field(default="")
    diagram_preference: str = Field(default="")
    task_preference: str = Field(default="")


class ProjectInfo(BaseModel):
    project_name: str = Field(default="")
    project_description: str = Field(default="")
    project_type: str = Field(default="")
    target_direction: str = Field(default="")
    available_equipment: str = Field(default="")
    current_focus: str = Field(default="")


class ReportGenerateRequest(BaseModel):
    profile: Profile
    project: ProjectInfo
    mode: str = Field(default="standard")


class ReportGenerateResponse(BaseModel):
    report_id: str
    filename: str
    markdown: str


class ReportStartResponse(BaseModel):
    report_id: str
    status: str


class ReportStatusResponse(BaseModel):
    report_id: str
    status: str
    current_step: str = ""
    progress: int = 0
    elapsed_seconds: int = 0
    total_steps: int = 0
    current_step_index: int = 0
    error: Optional[str] = None
    failed_step: Optional[str] = None
    markdown_url: Optional[str] = None
    pdf_url: Optional[str] = None
    html_url: Optional[str] = None
    completed_steps: list[str] = Field(default_factory=list)
