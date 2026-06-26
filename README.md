# 计算机项目知识地图生成 Agent

这是一个 Windows 本地运行的“项目预学习知识地图”工具。它的目标不是教你一步一步完整实现项目，也不是生成完整代码教程，而是在正式动手前帮助你快速建立项目认知，扫清知识盲区。

你可以输入一个计算机项目想法，例如：

- RV1126 + STM32 手势控制云台
- 3D 第一人称视角射击游戏
- AI 简历筛选系统
- 电商推荐系统
- 即时聊天软件
- 操作系统内核玩具项目
- 编译器
- 爬虫系统
- 智能健身饮食规划 App

系统会自动识别项目领域，拆解项目模块，提取必须理解的知识点，并生成一份适合 Markdown / HTML / PDF 阅读的“项目预学习知识地图”。

## 核心定位

本工具回答这些问题：

1. 这个项目到底是什么？
2. 它由哪些模块组成？
3. 涉及哪些核心知识点？
4. 每个知识点在项目中起什么作用？
5. 哪些知识点现在必须懂？
6. 哪些知识点后续再学？
7. 哪些知识点暂时不要深挖？
8. 开始动手前至少要扫清哪些盲区？
9. 哪些地方适合用图解帮助理解？
10. 最小切入口应该从哪里开始？

它不是完整项目教程、代码生成器、安装环境说明书或手把手实操手册。

## 输出模式

- 快速认知版：1500～2500 字。适合 10 分钟内了解项目全貌、核心知识点和暂时不用管的内容。
- 知识地图版：4000～7000 字。适合系统扫清知识盲区，建立完整项目认知。
- 认知深化版：8000～12000 字。适合导出 PDF 或 Obsidian 反复复习，但仍不写成完整教程。

## 报告结构

生成内容围绕以下结构：

1. 项目一句话解释
2. 项目领域识别
3. 项目总流程图
4. 项目模块拆解
5. 知识点总览清单
6. 知识点依赖关系
7. 核心知识点认知卡片
8. 硬件 / 电路 / 物理设备知识盲区
9. 关键图解清单
10. 初学者常见误区
11. 上手前自测问题
12. 最小切入口

如果项目不涉及硬件，第 8 章会明确写“本项目不涉及明显硬件部分，本章略”。如果项目涉及游戏、Web、AI、系统底层或爬虫，报告会补充对应领域的认知盲区。

## 运行方式

项目使用相对路径定位项目根目录，不依赖固定的本机盘符。无论你把项目放在 `E:\`、`D:\`，还是别人从 GitHub clone 到其他目录，只要在项目根目录执行下面的命令即可。

第一次运行先安装依赖：

```powershell
cd 项目目录
.\scripts\install_deps.ps1
```

`install_deps.ps1` 会自动检查项目根目录下的 `.venv`。如果 `.venv` 不存在，脚本会先创建虚拟环境，再安装 `requirements.txt` 中的依赖。

启动服务：

```powershell
cd 项目目录
.\scripts\start.ps1
```

打开网页：

```text
http://127.0.0.1:8000
```

FastAPI 会直接托管前端页面，不需要单独启动前端服务。

如果 PowerShell 提示脚本执行策略限制，可以在当前 PowerShell 窗口临时允许本地脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 环境变量配置

项目不会把真实密钥提交到 GitHub。仓库只保留 `.env.example` 作为模板，你需要在本地复制一份 `.env`，再填入自己的模型密钥。

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` 示例：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

IMAGE_API_BASE_URL=https://your-image-api.example.com/v1
IMAGE_API_KEY=你的图片 API Key
IMAGE_MODEL=gpt-image-2
IMAGE_API_TIMEOUT=300
IMAGE_SIZE=768x768
```

不要上传 `.env`。`.gitignore` 已经排除了 `.env`、`.env.*`，但保留 `.env.example` 作为可上传模板。

## 个人画像配置

系统会读取 `data/profile.json` 作为个人学习画像。这个文件可能包含你的背景、求职目标和学习偏好，不建议上传到公开仓库。

仓库中可以上传的是脱敏模板：

```text
data/profile.example.json
```

如果本地没有 `data/profile.json`，应用启动时会自动创建一份默认配置。你也可以复制模板后再自行修改：

```powershell
Copy-Item data\profile.example.json data\profile.json
```

## 异步生成接口

前端使用异步任务生成，不会一直阻塞等待一个长 POST 请求：

```text
POST /api/report/start
GET  /api/report/status/{report_id}
GET  /api/report/export/{report_id}
GET  /api/report/export_pdf/{report_id}
GET  /api/report/log/{report_id}
```

状态接口会返回当前步骤、进度、耗时、失败步骤、错误信息和下载链接。

## 输出目录

每个报告使用独立目录：

```text
outputs\reports\{report_id}\
  sections\
    section_01.md
    section_02.md
  assets\
    fig_01_project_overview.png
    ...
  image_plan.json
  outline.md
  report.md
  report_pdf.md
  report.html
  report.pdf
  status.json
```

图片原始输出保存到：

```text
outputs\images\{report_id}\
  image_plan.json
  fig_01_project_overview.png
  fig_02_knowledge_overview.png
  ...
```

报告目录中的 `assets\` 会保存一份图片副本，用于 Markdown/HTML/PDF 的相对路径引用。

## 图片生成机制

生成正式报告前，系统会先生成 `image_plan`。每一项包含：

- image_id
- knowledge_point
- title
- purpose
- image_type
- importance_level
- prompt
- filename
- target_section

图片类型分为：

- 结构图：程序用 Python 生成，用于项目全貌、知识点总览、知识点分级、最小切入口。
- AI 插图：调用图片 API，用于核心知识点卡片、抽象概念类比图、常见误区图、场景漫画图。
- 手动补图：如果图片 API 失败，Markdown 中会保留占位卡片，包含标题、用途、失败原因、prompt 和建议文件名。

图片 API 返回格式兼容：

- Markdown 图片格式：`![image](https://xxx.png)`
- 纯 URL
- `data[0].b64_json`
- `data[0].base64`
- `data[0].image_base64`
- `choices[0].message.content`

日志保存到：

```text
logs\{report_id}.log
```

日志会记录 report_id、开始时间、每一步开始/结束、模型请求失败、图片生成失败、Mermaid 渲染失败和 PDF 导出失败原因。

## GitHub 上传建议

建议上传这些内容：

- `backend/`
- `frontend/`
- `scripts/`
- `examples/`
- `README.md`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `data/profile.example.json`
- `test_image_api.py`

不要上传这些本地文件或运行产物：

- `.env`
- `.venv/`
- `.venv_anaconda_backup/`
- `.idea/`
- `data/profile.json`
- `logs/`
- `outputs/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`

首次上传可以使用：

```powershell
git init
git add .gitignore README.md requirements.txt .env.example backend frontend scripts examples data\profile.example.json test_image_api.py
git status
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

提交前建议先执行 `git status`，确认没有 `.env`、`.venv/`、`logs/`、`outputs/` 或 `data/profile.json`。

## 注意事项

- 不使用 Anaconda。
- 不使用 Docker。
- 不使用数据库。
- 不使用全局 Python。
- 不上传 `.env`。
- 不上传个人画像 `data/profile.json`。
- 不上传运行输出 `outputs/` 和日志 `logs/`。
- 所有项目代码、配置模板、输出、报告、图解和日志都保存在项目根目录下。
