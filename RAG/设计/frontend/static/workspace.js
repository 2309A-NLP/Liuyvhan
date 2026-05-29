const STORAGE_KEY = "rag-workspace-v5";

const state = {
    user: null,
    roles: [],
    selectedRoleId: "",
    sessionId: "",
    sessions: [],
    messages: [],
    references: [],
    memorySize: 0,
    isSending: false,
};

const elements = {
    controlRail: document.querySelector("#control-rail"),
    railToggle: document.querySelector("#rail-toggle"),
    guestLoginButton: document.querySelector("#guest-login-btn"),
    logoutButton: document.querySelector("#logout-btn"),
    userForm: document.querySelector("#user-form"),
    nameInput: document.querySelector("#name-input"),
    loginTag: document.querySelector("#login-tag"),
    userIdValue: document.querySelector("#user-id-value"),
    userAvatar: document.querySelector("#user-avatar"),
    userDisplayName: document.querySelector("#user-display-name"),
    selectedRoleLabel: document.querySelector("#selected-role-label"),
    newSessionButton: document.querySelector("#new-session-btn"),
    activeSessionName: document.querySelector("#active-session-name"),
    sessionIdValue: document.querySelector("#session-id-value"),
    memorySize: document.querySelector("#memory-size"),
    roleList: document.querySelector("#role-list"),
    sessionList: document.querySelector("#session-list"),
    chatTitle: document.querySelector("#chat-title"),
    chatSubtitle: document.querySelector("#chat-subtitle"),
    healthBadge: document.querySelector("#health-badge"),
    healthStatus: document.querySelector("#health-status"),
    healthMeta: document.querySelector("#health-meta"),
    messageList: document.querySelector("#message-list"),
    chatForm: document.querySelector("#chat-form"),
    messageInput: document.querySelector("#message-input"),
    composerTip: document.querySelector("#composer-tip"),
    sendButton: document.querySelector("#send-btn"),
    referencesList: document.querySelector("#references-list"),
};

function createId(prefix) {
    if (window.crypto?.randomUUID) {
        return `${prefix}-${window.crypto.randomUUID().slice(0, 8)}`;
    }
    return `${prefix}-${Date.now()}`;
}

function createGuestName() {
    return `访客${Math.floor(Math.random() * 900 + 100)}`;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function parseInlineMarkdown(text) {
    const stash = [];
    let html = escapeHtml(text);

    html = html.replace(/`([^`]+)`/g, (_, code) => {
        stash.push(`<code>${code}</code>`);
        return `__INLINE_${stash.length - 1}__`;
    });

    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

    return html.replace(/__INLINE_(\d+)__/g, (_, index) => stash[Number(index)]);
}

function markdownToHtml(markdown) {
    const codeBlocks = [];
    let source = String(markdown || "").replace(/\r\n/g, "\n");

    source = source.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const block = `<pre><code class="language-${escapeHtml(lang || "plain")}">${escapeHtml(code)}</code></pre>`;
        codeBlocks.push(block);
        return `@@CODEBLOCK_${codeBlocks.length - 1}@@`;
    });

    const lines = source.split("\n");
    const html = [];
    let listType = "";
    let paragraph = [];
    let quote = [];

    function flushParagraph() {
        if (!paragraph.length) {
            return;
        }
        html.push(`<p>${parseInlineMarkdown(paragraph.join("<br>"))}</p>`);
        paragraph = [];
    }

    function flushQuote() {
        if (!quote.length) {
            return;
        }
        html.push(`<blockquote>${quote.map((line) => `<p>${parseInlineMarkdown(line)}</p>`).join("")}</blockquote>`);
        quote = [];
    }

    function closeList() {
        if (!listType) {
            return;
        }
        html.push(`</${listType}>`);
        listType = "";
    }

    for (const line of lines) {
        if (!line.trim()) {
            flushParagraph();
            flushQuote();
            closeList();
            continue;
        }

        const codeMatch = line.match(/^@@CODEBLOCK_(\d+)@@$/);
        if (codeMatch) {
            flushParagraph();
            flushQuote();
            closeList();
            html.push(codeBlocks[Number(codeMatch[1])]);
            continue;
        }

        const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
        if (headingMatch) {
            flushParagraph();
            flushQuote();
            closeList();
            const level = headingMatch[1].length;
            html.push(`<h${level}>${parseInlineMarkdown(headingMatch[2])}</h${level}>`);
            continue;
        }

        if (line.startsWith("> ")) {
            flushParagraph();
            closeList();
            quote.push(line.slice(2));
            continue;
        }

        const orderedMatch = line.match(/^\d+\.\s+(.*)$/);
        if (orderedMatch) {
            flushParagraph();
            flushQuote();
            if (listType && listType !== "ol") {
                closeList();
            }
            if (!listType) {
                listType = "ol";
                html.push("<ol>");
            }
            html.push(`<li>${parseInlineMarkdown(orderedMatch[1])}</li>`);
            continue;
        }

        const unorderedMatch = line.match(/^[-*]\s+(.*)$/);
        if (unorderedMatch) {
            flushParagraph();
            flushQuote();
            if (listType && listType !== "ul") {
                closeList();
            }
            if (!listType) {
                listType = "ul";
                html.push("<ul>");
            }
            html.push(`<li>${parseInlineMarkdown(unorderedMatch[1])}</li>`);
            continue;
        }

        flushQuote();
        closeList();
        paragraph.push(line);
    }

    flushParagraph();
    flushQuote();
    closeList();
    return html.join("");
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });
    if (!response.ok) {
        let detail = "请求失败";
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch {
            detail = response.statusText || detail;
        }
        throw new Error(detail);
    }
    return response.json();
}

function loadState() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
        state.user = saved.user || null;
        state.selectedRoleId = saved.selectedRoleId || "";
        state.sessionId = saved.sessionId || "";
        state.sessions = Array.isArray(saved.sessions) ? saved.sessions : [];
    } catch {
        state.user = null;
        state.selectedRoleId = "";
        state.sessionId = "";
        state.sessions = [];
    }
}

function saveState() {
    localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
            user: state.user,
            selectedRoleId: state.selectedRoleId,
            sessionId: state.sessionId,
            sessions: state.sessions,
        }),
    );
}

function getSelectedRole() {
    return state.roles.find((item) => item.role_id === state.selectedRoleId) || null;
}

function findRoleById(roleId) {
    return state.roles.find((item) => item.role_id === roleId) || null;
}

function getSessionMeta(sessionId) {
    return state.sessions.find((item) => item.id === sessionId) || null;
}

function ensureSession() {
    if (state.sessionId && getSessionMeta(state.sessionId)) {
        return true;
    }
    if (!state.selectedRoleId) {
        return false;
    }
    createSession(state.selectedRoleId);
    return true;
}

function createSession(roleId = state.selectedRoleId) {
    const role = findRoleById(roleId) || getSelectedRole();
    const nextId = createId("session");
    const session = {
        id: nextId,
        title: role ? `${role.name} 对话` : "新会话",
        preview: "还没有消息",
        updatedAt: new Date().toISOString(),
        roleId: role?.role_id || roleId || state.selectedRoleId || "",
    };
    state.selectedRoleId = session.roleId;
    state.sessions = [session, ...state.sessions.filter((item) => item.id !== nextId)].slice(0, 20);
    state.sessionId = nextId;
    state.messages = [];
    state.references = [];
    state.memorySize = 0;
    saveState();
}

function updateSessionMeta(patch) {
    const current = getSessionMeta(state.sessionId) || {
        id: state.sessionId,
        title: "新会话",
        preview: "还没有消息",
        updatedAt: new Date().toISOString(),
        roleId: state.selectedRoleId,
    };
    const merged = {
        ...current,
        ...patch,
        id: state.sessionId,
        updatedAt: patch.updatedAt || new Date().toISOString(),
    };
    state.sessions = [merged, ...state.sessions.filter((item) => item.id !== state.sessionId)].slice(0, 20);
    saveState();
}

function formatDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    return new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function roleBadge(role) {
    const map = {
        virtual_friend: "友",
        psychologist: "心",
        legal_consultant: "法",
        wealth_advisor: "财",
        doctor: "医",
    };
    return map[role.role_id] || String(role.name || "角").slice(0, 1);
}

function renderStatus() {
    const displayName = state.user?.name || "未登录";
    const role = getSelectedRole();
    const sessionMeta = getSessionMeta(state.sessionId);

    elements.userDisplayName.textContent = displayName;
    elements.userAvatar.textContent = displayName.slice(0, 1).toUpperCase();
    elements.loginTag.textContent = state.user ? "已登录，可以开始对话。" : "请先进入一个身份。";
    elements.userIdValue.textContent = state.user?.user_id || "-";
    elements.selectedRoleLabel.textContent = role ? role.name : "未选择";
    elements.activeSessionName.textContent = sessionMeta?.title || "未开始";
    elements.sessionIdValue.textContent = state.sessionId || "-";
    elements.memorySize.textContent = String(state.memorySize || 0);
    elements.sendButton.disabled = !(state.user && state.selectedRoleId);
    elements.newSessionButton.disabled = !state.selectedRoleId;
    elements.composerTip.textContent = state.user && state.selectedRoleId
        ? "按 Enter 发送，Shift + Enter 换行。"
        : "登录并选择角色后才能发送消息。";
}

function renderRoles() {
    if (!state.roles.length) {
        elements.roleList.innerHTML = `
            <article class="placeholder-card">
                <strong>暂无角色</strong>
                <p>请检查角色种子数据是否已经成功加载。</p>
            </article>
        `;
        return;
    }

    if (!state.selectedRoleId || !getSelectedRole()) {
        state.selectedRoleId = state.roles[0].role_id;
    }

    elements.roleList.innerHTML = state.roles
        .map((role) => `
            <button type="button" class="role-card role-card-main role-card-${role.role_id} ${role.role_id === state.selectedRoleId ? "active" : ""}" data-role-id="${role.role_id}">
                <div class="role-top">
                    <div class="role-preview-top">
                        <div class="role-badge">${escapeHtml(roleBadge(role))}</div>
                        <div class="role-card-meta">
                            <strong>${escapeHtml(role.name)}</strong>
                            <div class="role-domain">${escapeHtml(role.domain)}</div>
                        </div>
                    </div>
                    <span class="role-action">点击即新建会话</span>
                </div>
                <div class="role-card-body">
                    <p>${escapeHtml(role.description)}</p>
                    <span class="role-tone">${escapeHtml(role.tone)}</span>
                </div>
            </button>
        `)
        .join("");

    elements.roleList.querySelectorAll("[data-role-id]").forEach((button) => {
        button.addEventListener("click", () => {
            const roleId = button.dataset.roleId || "";
            if (!roleId) {
                return;
            }
            createSession(roleId);
            renderRoles();
            renderChatHeader();
            renderStatus();
            renderSessions();
            renderMessages();
            renderReferences();
            closeRailOnMobile();
        });
    });
}

function renderSessions() {
    if (!state.sessions.length) {
        elements.sessionList.innerHTML = `
            <article class="placeholder-card">
                <strong>暂无会话</strong>
                <p>点击角色或“新建会话”后，这里会显示你的会话列表。</p>
            </article>
        `;
        return;
    }

    elements.sessionList.innerHTML = state.sessions
        .map((session) => `
            <button type="button" class="session-card ${session.id === state.sessionId ? "active" : ""}" data-session-id="${session.id}">
                <div class="session-top">
                    <strong>${escapeHtml(session.title || "新会话")}</strong>
                    <span class="session-time">${escapeHtml(formatDateTime(session.updatedAt))}</span>
                </div>
                <p>${escapeHtml(session.preview || "还没有消息")}</p>
            </button>
        `)
        .join("");

    elements.sessionList.querySelectorAll("[data-session-id]").forEach((button) => {
        button.addEventListener("click", async () => {
            state.sessionId = button.dataset.sessionId || "";
            const sessionMeta = getSessionMeta(state.sessionId);
            if (sessionMeta?.roleId) {
                state.selectedRoleId = sessionMeta.roleId;
            }
            state.references = [];
            state.memorySize = 0;
            saveState();
            renderRoles();
            renderChatHeader();
            renderStatus();
            renderSessions();
            renderReferences();
            await loadHistory();
            closeRailOnMobile();
        });
    });
}

function renderChatHeader() {
    const role = getSelectedRole();
    const sessionMeta = getSessionMeta(state.sessionId);
    if (role) {
        elements.chatTitle.textContent = sessionMeta?.title || `与 ${role.name} 开始新对话`;
        elements.chatSubtitle.textContent = sessionMeta
            ? `${role.name} · ${role.description}`
            : `当前角色：${role.name}。点击下方输入框即可开始这段新对话。`;
        return;
    }
    elements.chatTitle.textContent = "开始新的角色对话";
    elements.chatSubtitle.textContent = "先选择一个角色，系统会自动创建对应的新会话。";
}

function renderMessages() {
    if (!state.messages.length) {
        const placeholderTitle = state.selectedRoleId ? "工作台已就绪" : "先选择一个角色";
        const placeholderText = state.selectedRoleId
            ? "系统已经为该角色创建好新会话，直接输入问题即可开始。"
            : "点击上方任一角色卡片，系统会自动创建对应的新会话。";
        elements.messageList.innerHTML = `
            <article class="placeholder-card chat-placeholder">
                <strong>${placeholderTitle}</strong>
                <p>${placeholderText}</p>
            </article>
        `;
        return;
    }

    elements.messageList.innerHTML = state.messages
        .map((message) => {
            const type = message.role === "user" ? "user" : "assistant";
            const author = type === "user" ? (state.user?.name || "用户") : (getSelectedRole()?.name || "AI");
            const label = type === "user" ? "用户" : "角色回复";
            const content = message.content || (message.pending ? "正在生成..." : "");
            return `
                <article class="message ${type}">
                    <div class="message-meta">
                        <span class="message-tag">${escapeHtml(label)}</span>
                        <span>${escapeHtml(author)}</span>
                        <span class="message-dot"></span>
                        <span>${escapeHtml(formatDateTime(message.timestamp))}</span>
                    </div>
                    <div class="message-bubble">
                        <div class="message-content">${markdownToHtml(content)}</div>
                    </div>
                </article>
            `;
        })
        .join("");

    elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderReferences() {
    if (!state.references.length) {
        elements.referencesList.innerHTML = `
            <article class="placeholder-card">
                <strong>暂无引用</strong>
                <p>发送消息后，命中的知识片段会显示在这里。</p>
            </article>
        `;
        return;
    }

    elements.referencesList.innerHTML = state.references
        .map((item) => `
            <article class="reference-card">
                <div class="reference-top">
                    <strong>${escapeHtml(item.title || item.doc_id || "未命名资料")}</strong>
                    <span class="reference-score">相关度 ${Number(item.score || 0).toFixed(2)}</span>
                </div>
                <p>${escapeHtml(item.content || "")}</p>
                <div class="reference-meta">
                    <span class="reference-pill">${escapeHtml(item.source || "未知来源")}</span>
                    <span class="reference-pill">${escapeHtml(item.doc_id || "片段")}</span>
                </div>
            </article>
        `)
        .join("");
}

async function fetchHealth() {
    try {
        const health = await requestJson("/health", { method: "GET" });
        elements.healthStatus.textContent = "运行正常";
        elements.healthMeta.textContent = `${health.llm_provider} / ${health.embedding_backend} / ${health.storage_mode}`;
        elements.healthBadge.classList.add("online");
    } catch (error) {
        elements.healthStatus.textContent = "服务异常";
        elements.healthMeta.textContent = error.message;
        elements.healthBadge.classList.remove("online");
    }
}

async function fetchRoles() {
    state.roles = await requestJson("/roles", { method: "GET" });
    const sessionMeta = getSessionMeta(state.sessionId);
    if (sessionMeta?.roleId) {
        state.selectedRoleId = sessionMeta.roleId;
    } else if (!state.selectedRoleId && state.roles.length) {
        state.selectedRoleId = state.roles[0].role_id;
    }
    renderRoles();
    renderChatHeader();
    renderStatus();
    saveState();
}

async function login(name) {
    state.user = await requestJson("/users", {
        method: "POST",
        body: JSON.stringify({
            user_id: state.user?.user_id,
            name,
            profile: {},
        }),
    });
    saveState();
    renderStatus();
}

async function handleGuestLogin() {
    const button = elements.guestLoginButton;
    button.disabled = true;
    button.textContent = "进入中...";
    try {
        await login(createGuestName());
    } catch (error) {
        alert(`游客登录失败：${error.message}`);
    } finally {
        button.disabled = false;
        button.textContent = "游客进入";
    }
}

async function handleNamedLogin(event) {
    event.preventDefault();
    const name = elements.nameInput.value.trim();
    if (!name) {
        elements.nameInput.focus();
        return;
    }

    const submitButton = elements.userForm.querySelector("button[type='submit']");
    submitButton.disabled = true;
    submitButton.textContent = "进入中...";
    try {
        await login(name);
    } catch (error) {
        alert(`登录失败：${error.message}`);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "进入";
    }
}

function logout() {
    state.user = null;
    state.references = [];
    state.memorySize = 0;
    elements.nameInput.value = "";
    saveState();
    renderStatus();
    renderReferences();
}

async function loadHistory() {
    if (!state.sessionId) {
        state.messages = [];
        renderMessages();
        return;
    }

    try {
        const payload = await requestJson(`/sessions/${encodeURIComponent(state.sessionId)}/history`, {
            method: "GET",
        });
        state.messages = payload.messages || [];
        renderMessages();
    } catch (error) {
        console.error("Failed to load session history.", error);
        if (!state.messages.length) {
            renderMessages();
        }
    }
}

function appendPendingTurn(userMessage) {
    const timestamp = new Date().toISOString();
    state.messages = [
        ...state.messages,
        { role: "user", content: userMessage, timestamp },
        { role: "assistant", content: "", timestamp, pending: true },
    ];
    renderMessages();
    return state.messages.length - 1;
}

function updateAssistantDraft(messageIndex, content, pending = true) {
    const nextMessages = [...state.messages];
    const current = nextMessages[messageIndex];
    if (!current) {
        return;
    }
    nextMessages[messageIndex] = {
        ...current,
        content,
        pending,
    };
    state.messages = nextMessages;
    renderMessages();
}

function removeAssistantDraft(messageIndex) {
    state.messages = state.messages.filter((_, index) => index !== messageIndex);
    renderMessages();
}

async function streamChat(message, assistantIndex) {
    const response = await fetch("/chat/stream", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            session_id: state.sessionId,
            user_id: state.user.user_id,
            role_id: state.selectedRoleId,
            message,
        }),
    });

    if (!response.ok) {
        let detail = "请求失败";
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch {
            detail = response.statusText || detail;
        }
        throw new Error(detail);
    }

    if (!response.body) {
        throw new Error("浏览器未返回可读取的响应流。");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let answer = "";
    let completed = false;

    function handleEvent(line) {
        if (!line.trim()) {
            return;
        }

        const event = JSON.parse(line);
        if (event.type === "chunk") {
            answer += event.content || "";
            updateAssistantDraft(assistantIndex, answer, true);
            return;
        }

        if (event.type === "done") {
            answer = event.answer || answer;
            updateAssistantDraft(assistantIndex, answer, false);
            state.references = event.references || [];
            state.memorySize = event.memory_size ?? state.memorySize;
            completed = true;
            return;
        }

        if (event.type === "error") {
            throw new Error(event.detail || "生成回答时发生错误。");
        }
    }

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
            handleEvent(line);
        }

        if (done) {
            break;
        }
    }

    if (buffer.trim()) {
        handleEvent(buffer);
    }

    if (!completed) {
        updateAssistantDraft(assistantIndex, answer, false);
    }
}

function buildSessionTitle(message) {
    const role = getSelectedRole();
    const plain = message.replace(/\s+/g, " ").trim();
    if (!plain) {
        return role ? `${role.name} 对话` : "新会话";
    }
    return `${role ? `${role.name} · ` : ""}${plain.slice(0, 16)}`;
}

async function sendMessage(event) {
    event.preventDefault();
    const message = elements.messageInput.value.trim();
    if (!message || !state.user || !state.selectedRoleId || state.isSending) {
        return;
    }

    if (!ensureSession()) {
        return;
    }
    renderStatus();
    renderSessions();

    state.isSending = true;
    elements.sendButton.disabled = true;
    elements.sendButton.textContent = "发送中...";
    elements.messageInput.value = "";

    const assistantIndex = appendPendingTurn(message);
    updateSessionMeta({
        title: buildSessionTitle(message),
        preview: message.slice(0, 28),
        roleId: state.selectedRoleId,
    });
    renderStatus();
    renderSessions();
    renderChatHeader();

    try {
        await streamChat(message, assistantIndex);
        renderReferences();
        renderStatus();
        renderSessions();
        renderChatHeader();
    } catch (error) {
        removeAssistantDraft(assistantIndex);
        alert(`发送失败：${error.message}`);
    } finally {
        state.isSending = false;
        elements.sendButton.disabled = !(state.user && state.selectedRoleId);
        elements.sendButton.textContent = "发送";
    }
}

function closeRailOnMobile() {
    if (window.innerWidth <= 1180) {
        elements.controlRail.classList.remove("open");
    }
}

function toggleRail() {
    elements.controlRail.classList.toggle("open");
}

function bindEvents() {
    elements.railToggle.addEventListener("click", toggleRail);
    elements.guestLoginButton.addEventListener("click", handleGuestLogin);
    elements.logoutButton.addEventListener("click", logout);
    elements.userForm.addEventListener("submit", handleNamedLogin);
    elements.newSessionButton.addEventListener("click", async () => {
        if (!state.selectedRoleId) {
            return;
        }
        createSession(state.selectedRoleId);
        renderStatus();
        renderSessions();
        renderChatHeader();
        renderMessages();
        renderReferences();
        await loadHistory();
        closeRailOnMobile();
    });
    elements.chatForm.addEventListener("submit", sendMessage);
    elements.messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            elements.chatForm.requestSubmit();
        }
    });
    window.addEventListener("resize", () => {
        if (window.innerWidth > 1180) {
            elements.controlRail.classList.remove("open");
        }
    });
    document.addEventListener("click", (event) => {
        if (window.innerWidth > 1180 || !elements.controlRail.classList.contains("open")) {
            return;
        }
        const target = event.target;
        if (!(target instanceof Node)) {
            return;
        }
        if (elements.controlRail.contains(target) || elements.railToggle.contains(target)) {
            return;
        }
        closeRailOnMobile();
    });
}

async function init() {
    loadState();
    bindEvents();
    renderStatus();
    renderRoles();
    renderSessions();
    renderChatHeader();
    renderMessages();
    renderReferences();
    if (state.user?.name) {
        elements.nameInput.value = state.user.name;
    }
    await Promise.allSettled([fetchHealth(), fetchRoles()]);
    await loadHistory();
}

init();
