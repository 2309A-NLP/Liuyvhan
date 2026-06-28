const chatForm = document.getElementById("chat-form");
const queryInput = document.getElementById("query-input");
const userIdInput = document.getElementById("user-id");
const sessionIdInput = document.getElementById("session-id");
const submitBtn = document.getElementById("submit-btn");
const initDbBtn = document.getElementById("init-db-btn");
const statusStrip = document.getElementById("status-strip");
const statusText = document.getElementById("status-text");
const messageOutput = document.getElementById("message-output");
const intentOutput = document.getElementById("intent-output");
const stateOutput = document.getElementById("state-output");
const jsonOutput = document.getElementById("json-output");
const traceList = document.getElementById("trace-list");
const copyJsonBtn = document.getElementById("copy-json-btn");

function setStatus(text, variant = "") {
    statusStrip.className = "status-strip";
    if (variant) {
        statusStrip.classList.add(variant);
    }
    statusText.textContent = text;
}

function renderResponse(payload) {
    messageOutput.textContent = payload.message || "-";
    intentOutput.textContent = payload.intent || "-";
    stateOutput.textContent = payload.state || "-";
    jsonOutput.textContent = JSON.stringify(payload, null, 2);

    const trace = Array.isArray(payload.trace) && payload.trace.length
        ? payload.trace
        : ["当前没有可展示的执行轨迹。"];
    traceList.innerHTML = trace.map((item) => `<li>${item}</li>`).join("");

    if (payload.success) {
        setStatus(`请求成功：${payload.state || "已完成"}`, "success");
    } else {
        setStatus(`请求完成：${payload.state || "需补充信息"}`, "error");
    }
}

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });

    const payload = await response.json();
    return { ok: response.ok, payload };
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = "健康助理思考中...";
    setStatus("正在调用健康助理...", "");

    const body = {
        user_id: Number(userIdInput.value),
        session_id: sessionIdInput.value.trim(),
        query: queryInput.value.trim(),
    };

    try {
        const { payload } = await postJson("/api/agent/chat", body);
        renderResponse(payload);
    } catch (error) {
        renderResponse({
            success: false,
            message: "前端请求失败，请检查服务是否已启动。",
            trace: [String(error)],
            data: {},
            intent: null,
            state: "FAILED",
        });
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "发送给健康助理";
    }
});

initDbBtn.addEventListener("click", async () => {
    initDbBtn.disabled = true;
    initDbBtn.textContent = "正在重置...";
    setStatus("正在重置测试数据库...", "");
    try {
        const { payload } = await postJson("/api/init-db", {});
        renderResponse(payload);
    } catch (error) {
        renderResponse({
            success: false,
            message: "数据库初始化请求失败。",
            trace: [String(error)],
            data: {},
            intent: null,
            state: "FAILED",
        });
    } finally {
        initDbBtn.disabled = false;
        initDbBtn.textContent = "重置测试数据库";
    }
});

document.querySelectorAll("[data-query]").forEach((button) => {
    button.addEventListener("click", () => {
        queryInput.value = button.dataset.query || "";
        queryInput.focus();
    });
});

copyJsonBtn.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(jsonOutput.textContent);
        copyJsonBtn.textContent = "已复制";
        setTimeout(() => {
            copyJsonBtn.textContent = "复制 JSON";
        }, 1200);
    } catch {
        copyJsonBtn.textContent = "复制失败";
        setTimeout(() => {
            copyJsonBtn.textContent = "复制 JSON";
        }, 1200);
    }
});
