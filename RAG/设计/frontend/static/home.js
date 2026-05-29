const WORKSPACE_STORAGE_KEY = "rag-workspace-v5";

const elements = {
    healthStatus: document.querySelector("#health-status"),
    healthMeta: document.querySelector("#health-meta"),
    roleCount: document.querySelector("#role-count"),
    storageMode: document.querySelector("#storage-mode"),
    rolePreviewList: document.querySelector("#role-preview-list"),
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
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

function roleBadge(roleId, roleName) {
    const map = {
        virtual_friend: "友",
        psychologist: "心",
        legal_consultant: "法",
        wealth_advisor: "财",
        doctor: "医",
    };
    return map[roleId] || String(roleName || "角").slice(0, 1);
}

function renderRolePreview(roles) {
    if (!roles.length) {
        elements.rolePreviewList.innerHTML = `
            <article class="placeholder-card">
                <strong>暂无角色</strong>
                <p>请检查后端是否已经成功加载角色种子数据。</p>
            </article>
        `;
        return;
    }

    elements.rolePreviewList.innerHTML = roles
        .map((role) => `
            <article class="role-preview-card">
                <div class="role-preview-top">
                    <div class="role-badge">${escapeHtml(roleBadge(role.role_id, role.name))}</div>
                    <div>
                        <strong>${escapeHtml(role.name)}</strong>
                        <div class="role-domain">${escapeHtml(role.domain)}</div>
                    </div>
                </div>
                <p>${escapeHtml(role.description)}</p>
                <span class="role-tone">${escapeHtml(role.tone)}</span>
            </article>
        `)
        .join("");
}

function updateWorkspaceHint(roles) {
    try {
        const saved = JSON.parse(localStorage.getItem(WORKSPACE_STORAGE_KEY) || "{}");
        const savedRole = roles.find((item) => item.role_id === saved.selectedRoleId);
        if (!saved.user?.name) {
            return;
        }

        const actionButton = document.querySelector(".hero-actions .primary-btn");
        if (!actionButton) {
            return;
        }

        actionButton.textContent = savedRole
            ? `继续使用 ${saved.user.name} · ${savedRole.name}`
            : `继续使用 ${saved.user.name}`;
    } catch {
        // Ignore invalid local state.
    }
}

async function init() {
    try {
        const [health, roles] = await Promise.all([
            requestJson("/health", { method: "GET" }),
            requestJson("/roles", { method: "GET" }),
        ]);

        elements.healthStatus.textContent = health.status === "ok" ? "运行正常" : health.status;
        elements.healthMeta.textContent = `${health.llm_provider} / ${health.embedding_backend}`;
        elements.roleCount.textContent = String(roles.length);
        elements.storageMode.textContent = health.storage_mode;
        renderRolePreview(roles);
        updateWorkspaceHint(roles);
    } catch (error) {
        elements.healthStatus.textContent = "服务异常";
        elements.healthMeta.textContent = error.message;
        elements.roleCount.textContent = "-";
        elements.storageMode.textContent = "-";
        elements.rolePreviewList.innerHTML = `
            <article class="placeholder-card">
                <strong>加载失败</strong>
                <p>${escapeHtml(error.message)}</p>
            </article>
        `;
    }
}

init();
