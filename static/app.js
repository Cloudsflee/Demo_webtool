const userInputEl = document.getElementById("userInput");
const maxTurnsEl = document.getElementById("maxTurns");
const debugEl = document.getElementById("debug");
const runBtn = document.getElementById("runBtn");

const statusBadgeEl = document.getElementById("statusBadge");
const runInfoEl = document.getElementById("runInfo");
const requestOverviewEl = document.getElementById("requestOverview");
const answerHighlightsEl = document.getElementById("answerHighlights");
const toolTimelineEl = document.getElementById("toolTimeline");
const answerEl = document.getElementById("answer");
const imageSummaryEl = document.getElementById("imageSummary");
const imageGalleryEl = document.getElementById("imageGallery");
const metaEl = document.getElementById("meta");
const debugLogsEl = document.getElementById("debugLogs");

function stringify(data) {
  return JSON.stringify(data, null, 2);
}

function truncate(text, maxLen = 120) {
  const raw = String(text || "").trim();
  if (!raw) return "-";
  return raw.length > maxLen ? `${raw.slice(0, maxLen)}...` : raw;
}

function nowLabel() {
  return new Date().toLocaleString();
}

function setStatus(kind, text) {
  statusBadgeEl.className = `status-badge status-${kind}`;
  statusBadgeEl.textContent = text;
}

function toolDisplayName(name) {
  if (name === "web_search") return "网页搜索";
  if (name === "web_crawler") return "网页抓取";
  if (name === "image_search") return "图片搜索";
  if (name === "image_crawl") return "图片抓取";
  if (name === "image_fetch_save") return "图片下载保存";
  return name || "unknown_tool";
}

function extractToolCore(call) {
  const args = call?.args || {};

  if (call?.name === "web_search") {
    const query = truncate(args.query || "未提供查询词", 90);
    const type = args.searchType || args.type || "search";
    const ext = [];
    if (args.dataRange) ext.push(`时间=${args.dataRange}`);
    if (args.page !== undefined) ext.push(`页=${args.page}`);
    if (args.location) ext.push(`地区=${args.location}`);
    const suffix = ext.length ? `（${ext.join("，")}）` : "";
    return `关键词：${query}，类型：${type}${suffix}`;
  }

  if (call?.name === "web_crawler") {
    const urlRaw = String(args.url || "").trim();
    if (!urlRaw) return "抓取页面：未提供 URL";
    const includeMarkdown = args.includeMarkdown === false ? "文本优先" : "Markdown优先";
    try {
      const parsed = new URL(urlRaw);
      return `抓取目标：${parsed.host}${parsed.pathname || "/"}（${includeMarkdown}）`;
    } catch {
      return `抓取目标：${truncate(urlRaw, 90)}（${includeMarkdown}）`;
    }
  }

  if (call?.name === "image_search") {
    const query = truncate(args.query || "未提供查询词", 90);
    const limit = args.limit ?? 10;
    const timeRange = args.timeRange ? `，时间=${args.timeRange}` : "";
    return `图片查询：${query}，数量=${limit}${timeRange}`;
  }

  if (call?.name === "image_crawl") {
    const urlRaw = String(args.url || "").trim();
    return `图片抓取页面：${truncate(urlRaw || "未提供 URL", 100)}`;
  }

  if (call?.name === "image_fetch_save") {
    const imageUrl = truncate(args.imageUrl || "未提供图片 URL", 90);
    const sourcePage = truncate(args.sourcePage || "未提供来源页", 80);
    return `下载图片：${imageUrl}，来源：${sourcePage}`;
  }

  return `参数：${truncate(stringify(args), 120)}`;
}

function extractAnswerHighlights(answer) {
  const raw = String(answer || "").trim();
  if (!raw) return ["暂无回答内容。"];

  const slices = raw
    .split(/[\n。！？!?]/g)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 4)
    .map((s) => truncate(s, 110));

  return slices.length ? slices : [truncate(raw, 110)];
}

function renderRequestOverview(items) {
  requestOverviewEl.innerHTML = "";
  items.forEach((item) => {
    const box = document.createElement("div");
    box.className = "overview-item";

    const k = document.createElement("span");
    k.className = "k";
    k.textContent = item.key;

    const v = document.createElement("div");
    v.className = "v";
    v.textContent = item.value;

    box.appendChild(k);
    box.appendChild(v);
    requestOverviewEl.appendChild(box);
  });
}

function renderAnswerHighlights(answer) {
  const highlights = extractAnswerHighlights(answer);
  answerHighlightsEl.innerHTML = "";

  highlights.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    answerHighlightsEl.appendChild(li);
  });
}

function getToolDebugList(debugLogs) {
  return (Array.isArray(debugLogs) ? debugLogs : []).filter((item) => item && item.tool_name);
}

function renderToolTimeline(toolCalls, debugLogs) {
  toolTimelineEl.innerHTML = "";

  if (!toolCalls.length) {
    const empty = document.createElement("li");
    empty.className = "empty-block";
    empty.textContent = "本次请求未触发工具调用，模型直接给出了回答。";
    toolTimelineEl.appendChild(empty);
    return;
  }

  const toolDebugList = getToolDebugList(debugLogs);

  toolCalls.forEach((call, index) => {
    const step = document.createElement("li");
    step.className = "timeline-item";
    step.style.animationDelay = `${Math.min(index * 0.05, 0.35)}s`;

    const row = document.createElement("div");
    row.className = "tool-row";

    const no = document.createElement("span");
    no.className = "tool-no";
    no.textContent = String(index + 1);

    const name = document.createElement("span");
    name.className = "tool-name";
    name.textContent = toolDisplayName(call.name);

    const meta = document.createElement("span");
    meta.className = "tool-meta";
    const statusText = String(call.status || "").toLowerCase() === "ok" ? "成功" : "失败";
    meta.textContent = `${statusText} · HTTP ${call.http_status ?? "-"}`;

    row.appendChild(no);
    row.appendChild(name);
    row.appendChild(meta);

    const core = document.createElement("div");
    core.className = "tool-core";
    core.textContent = extractToolCore(call);

    const debug = toolDebugList[index];
    const tail = document.createElement("div");
    tail.className = "tool-tail";
    if (debug) {
      const turn = debug.turn ?? "-";
      const length = debug.tool_text_length ?? "-";
      tail.textContent = `执行轮次：${turn}，返回文本长度：${length}`;
    } else {
      tail.textContent = "无调试细节（可能未开启 debug）。";
    }

    step.appendChild(row);
    step.appendChild(core);
    step.appendChild(tail);
    toolTimelineEl.appendChild(step);
  });
}

function renderDownloadedImages(items) {
  imageGalleryEl.innerHTML = "";
  const list = Array.isArray(items) ? items : [];

  if (!list.length) {
    imageSummaryEl.textContent = "本次请求未下载图片。";
    const empty = document.createElement("div");
    empty.className = "empty-block";
    empty.textContent = "没有可展示的图片结果。可在提问中明确要求“下载并保存图片”。";
    imageGalleryEl.appendChild(empty);
    return;
  }

  imageSummaryEl.textContent = `本次请求共下载 ${list.length} 张图片。`;
  list.forEach((item) => {
    const card = document.createElement("article");
    card.className = "img-card";

    const img = document.createElement("img");
    img.className = "img-thumb";
    img.src = item.public_url || item.image_url || "";
    img.alt = item.file_name || "downloaded image";
    img.loading = "lazy";

    const body = document.createElement("div");
    body.className = "img-meta";
    body.innerHTML = `
      <div><strong>文件：</strong>${truncate(item.file_name || "-", 80)}</div>
      <div><strong>大小：</strong>${item.size ?? "-"} bytes</div>
      <div><strong>MIME：</strong>${truncate(item.mime || "-", 40)}</div>
      <div><strong>来源页：</strong><a href="${item.source_page || "#"}" target="_blank" rel="noopener noreferrer">${truncate(item.source_page || "-", 70)}</a></div>
      <div><strong>本地路径：</strong>${truncate(item.saved_path || "-", 90)}</div>
    `;

    card.appendChild(img);
    card.appendChild(body);
    imageGalleryEl.appendChild(card);
  });
}

function resetView() {
  answerEl.textContent = "";
  requestOverviewEl.innerHTML = "";
  answerHighlightsEl.innerHTML = "";
  toolTimelineEl.innerHTML = "";
  imageSummaryEl.textContent = "";
  imageGalleryEl.innerHTML = "";
  metaEl.textContent = "";
  debugLogsEl.textContent = "";
}

async function runAgent() {
  const userInput = userInputEl.value.trim();
  const maxTurns = Number(maxTurnsEl.value || 6);
  const debug = debugEl.checked;

  if (!userInput) {
    setStatus("error", "输入缺失");
    runInfoEl.textContent = "请先填写用户问题。";
    return;
  }

  runBtn.disabled = true;
  resetView();
  setStatus("running", "执行中");
  runInfoEl.textContent = `开始时间：${nowLabel()}`;

  try {
    const response = await fetch("/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: stringify({
        user_input: userInput,
        max_turns: maxTurns,
        debug,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      setStatus("error", "请求失败");
      runInfoEl.textContent = `失败时间：${nowLabel()}`;
      renderRequestOverview([
        { key: "用户输入", value: truncate(userInput, 120) },
        { key: "失败原因", value: String(data.error || response.statusText) },
        { key: "HTTP 状态", value: String(response.status) },
        { key: "执行参数", value: `max_turns=${maxTurns}, debug=${debug}` },
      ]);
      renderAnswerHighlights("");
      renderToolTimeline([], []);
      renderDownloadedImages([]);
      metaEl.textContent = stringify({ status: response.status, response: data });
      return;
    }

    const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls : [];
    const debugLogs = Array.isArray(data.debug_logs) ? data.debug_logs : [];
    const downloadedImages = Array.isArray(data.downloaded_images) ? data.downloaded_images : [];
    const answer = String(data.answer || "");
    const modelInfo = debugLogs.find((log) => log && Object.prototype.hasOwnProperty.call(log, "selected_model"));

    setStatus("ok", "已完成");
    runInfoEl.textContent = `完成时间：${nowLabel()}`;

    renderRequestOverview([
      { key: "用户诉求", value: truncate(userInput, 120) },
      { key: "调用链摘要", value: toolCalls.length ? toolCalls.map((x, i) => `${i + 1}.${toolDisplayName(x.name)}`).join(" → ") : "无工具调用" },
      { key: "执行轮数", value: String(data.turns ?? "-") },
      { key: "工具调用数", value: String(toolCalls.length) },
      { key: "请求标识", value: String(data.request_id || "-") },
      { key: "下载图片数", value: String(downloadedImages.length) },
      { key: "模型", value: modelInfo?.selected_model || "-" },
      { key: "模型选择", value: modelInfo?.auto_selected ? "自动选择" : "配置指定" },
    ]);

    renderAnswerHighlights(answer);
    renderToolTimeline(toolCalls, debugLogs);
    renderDownloadedImages(downloadedImages);
    answerEl.textContent = answer || "无回答内容。";

    metaEl.textContent = stringify({
      turns: data.turns,
      tool_calls_count: toolCalls.length,
      request_id: data.request_id || null,
      downloaded_images_count: downloadedImages.length,
      selected_model: modelInfo?.selected_model || null,
      configured_model: modelInfo?.configured_model || null,
      auto_selected: modelInfo?.auto_selected ?? null,
    });
    debugLogsEl.textContent = stringify(debugLogs);
  } catch (error) {
    setStatus("error", "网络异常");
    runInfoEl.textContent = `异常时间：${nowLabel()}`;
    renderRequestOverview([
      { key: "用户输入", value: truncate(userInput, 120) },
      { key: "异常信息", value: truncate(String(error), 150) },
      { key: "执行参数", value: `max_turns=${maxTurns}, debug=${debug}` },
      { key: "建议", value: "检查服务是否启动，以及网关/网络连通性。" },
    ]);
    renderAnswerHighlights("");
    renderToolTimeline([], []);
    renderDownloadedImages([]);
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runAgent);
