const fields = ["my_background", "job_goal", "learning_preference", "diagram_preference", "task_preference"];
const projectFields = ["project_name", "project_description", "project_type", "target_direction", "available_equipment", "current_focus"];

let currentReportId = "";
let currentFilename = "";
let currentMarkdownUrl = "";
let currentPdfUrl = "";
let currentHtmlUrl = "";
let pollTimer = null;

function el(id) {
  return document.getElementById(id);
}

function setMessage(text, isError = false) {
  const message = el("message");
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function collectProfile() {
  return Object.fromEntries(fields.map((id) => [id, el(id).value.trim()]));
}

function collectProject() {
  return Object.fromEntries(projectFields.map((id) => [id, el(id).value.trim()]));
}

function fillProfile(profile) {
  fields.forEach((id) => {
    el(id).value = profile[id] || "";
  });
}

function switchTab(mode) {
  const previewMode = mode === "preview";
  el("previewTab").classList.toggle("active", previewMode);
  el("sourceTab").classList.toggle("active", !previewMode);
  el("previewTab").setAttribute("aria-selected", String(previewMode));
  el("sourceTab").setAttribute("aria-selected", String(!previewMode));
  el("previewPane").classList.toggle("active", previewMode);
  el("sourcePane").classList.toggle("active", !previewMode);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function preprocessCallouts(markdown) {
  const map = {
    "重点": ["must", "必须掌握"],
    "常见坑": ["warn", "常见坑"],
    "任务": ["task", "最小实践任务"],
    "项目作用": ["info", "项目作用"],
  };
  return markdown.replace(/^\[(重点|常见坑|任务|项目作用)\]\s*(.+)$/gm, (_match, key, content) => {
    const [cssClass, label] = map[key];
    return `<div class="callout ${cssClass}"><strong>${label}</strong><p>${escapeHtml(content)}</p></div>`;
  });
}

function sanitizeMermaid(source) {
  const allowedStarts = ["graph ", "flowchart ", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "classDiagram", "erDiagram", "journey", "gantt", "pie", "mindmap", "timeline"];
  const trimmed = source.trim();
  const hasAllowedStart = allowedStarts.some((prefix) => trimmed.startsWith(prefix));
  if (!hasAllowedStart) return trimmed;
  return trimmed
    .split("\n")
    .map((line) => {
      let safe = line.replace(/[{}]/g, "").replace(/`/g, "'");
      safe = safe.replace(/\b[A-Za-z_][A-Za-z0-9_]*\([^)]*\)/g, "函数调用");
      safe = safe.replace(/\|([^|]{36,})\|/g, (_match, label) => `|${label.slice(0, 34)}...|`);
      safe = safe.replace(/\[([^\]]{46,})\]/g, (_match, label) => `[${label.slice(0, 44)}...]`);
      safe = safe.replace(/\(([^\)]{46,})\)/g, (_match, label) => `(${label.slice(0, 44)}...)`);
      return safe;
    })
    .join("\n");
}

function fallbackDiagram(source, errorMessage = "") {
  const hint = errorMessage ? `Mermaid 渲染失败，已降级为文本结构图。\n原因：${errorMessage}\n\n` : "";
  return `
    <div class="diagram-scroll diagram-clickable" title="点击放大查看">
      <pre class="mermaid-fallback">${escapeHtml(hint + source)}</pre>
    </div>
  `;
}

async function renderMermaidBlocks(preview) {
  const blocks = [...preview.querySelectorAll("pre code.language-mermaid, pre code.lang-mermaid")];
  if (!blocks.length || !window.mermaid) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "default",
    flowchart: { useMaxWidth: true, htmlLabels: false },
    sequence: { useMaxWidth: true },
  });

  for (const [index, block] of blocks.entries()) {
    const original = block.textContent;
    const sanitized = sanitizeMermaid(original);
    const wrapper = document.createElement("div");
    wrapper.className = "diagram-scroll diagram-clickable";
    wrapper.title = "点击放大查看";
    try {
      const result = await mermaid.render(`mermaid-${Date.now()}-${index}`, sanitized);
      wrapper.innerHTML = `<div class="diagram-inner">${result.svg}</div>`;
    } catch (error) {
      wrapper.innerHTML = fallbackDiagram(sanitized, error.message || "未知错误");
    }
    block.closest("pre").replaceWith(wrapper);
  }
}

function wrapWideElements(preview) {
  preview.querySelectorAll("table").forEach((table) => {
    if (table.parentElement.classList.contains("diagram-scroll")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "diagram-scroll";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

function resolveAssetLinks(preview) {
  if (!currentReportId) return;
  preview.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    if (!src || src.startsWith("http") || src.startsWith("/") || src.startsWith("data:")) return;
    img.src = `/reports/${currentReportId}/${src}`;
    img.classList.add("diagram-clickable");
    img.title = "点击放大查看";
  });
}

function attachDiagramZoom() {
  document.querySelectorAll(".diagram-clickable").forEach((diagram) => {
    diagram.addEventListener("click", () => {
      el("diagramModalBody").innerHTML = diagram.outerHTML || diagram.innerHTML;
      el("diagramModal").classList.add("active");
      el("diagramModal").setAttribute("aria-hidden", "false");
    });
  });
}

async function renderMarkdown(markdown) {
  const preview = el("markdownPreview");
  if (!markdown) {
    preview.className = "markdown-preview empty-state";
    preview.textContent = "生成后的项目预学习知识地图会显示在这里。";
    return;
  }
  preview.className = "markdown-preview";
  const processed = preprocessCallouts(markdown);
  if (window.marked) {
    preview.innerHTML = marked.parse(processed);
  } else {
    preview.innerHTML = `<pre>${escapeHtml(markdown)}</pre>`;
  }
  resolveAssetLinks(preview);
  wrapWideElements(preview);
  await renderMermaidBlocks(preview);
  attachDiagramZoom();
}

function resetProgress() {
  el("progressBar").style.width = "0%";
  el("progressText").textContent = "等待生成";
  el("elapsedText").textContent = "耗时 0 秒";
  el("reportIdBadge").textContent = "未开始";
  el("failureBox").classList.add("hidden");
  el("failureBox").textContent = "";
  el("finishedDownloads").classList.add("hidden");
  el("stepList").innerHTML = [
    "⬜ 等待接收项目主题",
    "⬜ 等待规划报告图片",
    "⬜ 等待生成报告图片",
    "⬜ 等待生成知识地图正文",
    "⬜ 等待导出 Markdown",
    "⬜ 等待导出 PDF",
  ].map((text) => `<li class="pending">${text}</li>`).join("");
}

function updateProgress(status) {
  el("progressBar").style.width = `${status.progress || 0}%`;
  el("progressText").textContent = status.current_step || status.status || "运行中";
  el("elapsedText").textContent = `耗时 ${status.elapsed_seconds || 0} 秒`;
  el("reportIdBadge").textContent = status.report_id ? `ID: ${status.report_id}` : "未开始";

  const completed = status.completed_steps || [];
  const current = status.status === "running" ? [`⏳ ${status.current_step}`] : [];
  const waiting = [];
  if (status.status !== "completed" && status.status !== "failed") {
    waiting.push("⬜ 等待后续步骤");
  }
  el("stepList").innerHTML = [...completed, ...current, ...waiting]
    .map((text) => `<li class="${text.startsWith("⏳") ? "running" : text.startsWith("⚠️") ? "failed" : ""}">${escapeHtml(text)}</li>`)
    .join("");

  if (status.status === "failed") {
    el("failureBox").classList.remove("hidden");
    el("failureBox").innerHTML = `
      <strong>生成失败</strong><br>
      失败步骤：${escapeHtml(status.failed_step || "未知")}<br>
      错误信息：${escapeHtml(status.error || "未知错误")}<br>
      建议：可以先切换到“快速认知版”重试；如果仍失败，请查看 logs/${status.report_id}.log。
    `;
  }

  if (status.status === "completed") {
    currentMarkdownUrl = status.markdown_url;
    currentPdfUrl = status.pdf_url;
    currentHtmlUrl = status.html_url;
    el("downloadMarkdownLink").href = currentMarkdownUrl;
    el("downloadPdfLink").href = currentPdfUrl;
    el("openHtmlLink").href = currentHtmlUrl;
    el("finishedDownloads").classList.remove("hidden");
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollStatus() {
  if (!currentReportId) return;
  try {
    const response = await fetch(`/api/report/status/${currentReportId}`);
    const status = await response.json();
    if (!response.ok) throw new Error(status.detail || "读取生成状态失败。");
    updateProgress(status);
    if (status.status === "completed") {
      stopPolling();
      setMessage("项目预学习知识地图生成完成。");
      el("generateBtn").disabled = false;
      el("generateBtn").textContent = "生成项目预学习知识地图";
      const mdResponse = await fetch(status.markdown_url);
      const markdown = await mdResponse.text();
      currentFilename = "report.md";
      el("markdownOutput").value = markdown;
      await renderMarkdown(markdown);
      switchTab("preview");
    }
    if (status.status === "failed") {
      stopPolling();
      setMessage(`生成失败：${status.failed_step || "未知步骤"}`, true);
      el("generateBtn").disabled = false;
      el("generateBtn").textContent = "生成项目预学习知识地图";
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("health failed");
    el("healthStatus").textContent = "后端正常";
  } catch {
    el("healthStatus").textContent = "后端异常";
  }
}

async function loadProfile() {
  const response = await fetch("/api/profile");
  if (!response.ok) {
    setMessage("读取个人基础失败。", true);
    return;
  }
  fillProfile(await response.json());
}

async function saveProfile() {
  const response = await fetch("/api/profile/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectProfile()),
  });
  if (!response.ok) {
    setMessage("保存个人基础失败。", true);
    return;
  }
  fillProfile(await response.json());
  setMessage("个人基础已保存。");
}

async function generateReport() {
  const project = collectProject();
  if (!project.project_name || !project.project_description) {
    setMessage("请至少填写项目名称和项目描述。", true);
    return;
  }

  stopPolling();
  resetProgress();
  el("generateBtn").disabled = true;
  el("generateBtn").textContent = "生成中";
  setMessage("已提交后台任务，正在启动生成流程。");

  try {
    const response = await fetch("/api/report/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: collectProfile(),
        project,
        mode: el("report_mode").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "启动知识地图任务失败。");
    currentReportId = data.report_id;
    el("reportIdBadge").textContent = `ID: ${currentReportId}`;
    pollTimer = setInterval(pollStatus, 1000);
    await pollStatus();
  } catch (error) {
    setMessage(error.message, true);
    el("generateBtn").disabled = false;
    el("generateBtn").textContent = "生成项目预学习知识地图";
  }
}

async function copyMarkdown() {
  const markdown = el("markdownOutput").value;
  if (!markdown) {
    setMessage("当前没有可复制的知识地图。", true);
    return;
  }
  await navigator.clipboard.writeText(markdown);
  setMessage("已复制 Markdown 全文。");
}

function downloadUrl(url, fallbackName) {
  if (!url) {
    setMessage("请先生成知识地图。", true);
    return;
  }
  const link = document.createElement("a");
  link.href = url;
  link.download = fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function exportMarkdown() {
  downloadUrl(currentMarkdownUrl || (currentReportId ? `/api/report/export/${currentReportId}` : ""), "report.md");
}

async function exportPdf() {
  if (currentPdfUrl) {
    downloadUrl(currentPdfUrl, "report.pdf");
    return;
  }
  const preview = el("markdownPreview");
  if (!el("markdownOutput").value) {
    setMessage("请先生成知识地图。", true);
    return;
  }
  if (!window.html2pdf) {
    setMessage("PDF 导出组件未加载，请检查网络或 CDN。", true);
    return;
  }
  switchTab("preview");
  setMessage("正在从预览页面导出 PDF。");
  try {
    await html2pdf().set({
      margin: [8, 8, 8, 8],
      filename: "project_prelearning_report.pdf",
      image: { type: "jpeg", quality: 0.96 },
      html2canvas: { scale: 2, useCORS: true, scrollX: 0, scrollY: 0 },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"], avoid: [".diagram-scroll", "table", "pre"] },
    }).from(preview).save();
    setMessage("PDF 已导出。");
  } catch (error) {
    setMessage(`PDF 导出失败：${error.message}`, true);
  }
}

function clearInputs() {
  projectFields.forEach((id) => {
    if (el(id).tagName === "SELECT") el(id).selectedIndex = 0;
    else el(id).value = "";
  });
  stopPolling();
  el("markdownOutput").value = "";
  currentReportId = "";
  currentFilename = "";
  currentMarkdownUrl = "";
  currentPdfUrl = "";
  currentHtmlUrl = "";
  renderMarkdown("");
  resetProgress();
  el("generateBtn").disabled = false;
  el("generateBtn").textContent = "生成项目预学习知识地图";
  setMessage("项目信息和输出已清空。");
}

function closeDiagramModal() {
  el("diagramModal").classList.remove("active");
  el("diagramModal").setAttribute("aria-hidden", "true");
  el("diagramModalBody").innerHTML = "";
}

document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadProfile();
  renderMarkdown("");
  resetProgress();
  el("saveProfileBtn").addEventListener("click", saveProfile);
  el("generateBtn").addEventListener("click", generateReport);
  el("copyBtn").addEventListener("click", copyMarkdown);
  el("exportBtn").addEventListener("click", exportMarkdown);
  el("exportPdfBtn").addEventListener("click", exportPdf);
  el("clearBtn").addEventListener("click", clearInputs);
  el("previewTab").addEventListener("click", () => switchTab("preview"));
  el("sourceTab").addEventListener("click", () => switchTab("source"));
  el("closeDiagramModal").addEventListener("click", closeDiagramModal);
  el("diagramModal").addEventListener("click", (event) => {
    if (event.target === el("diagramModal")) closeDiagramModal();
  });
});
