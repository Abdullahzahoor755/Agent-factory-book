const navLinks = document.querySelectorAll(".nav-link");
const currentPath = window.location.pathname.split("/").pop() || "index.html";
const menuToggle = document.querySelector(".mobile-menu-toggle");
const sidebar = document.querySelector(".sidebar");
const revealItems = document.querySelectorAll(".reveal");
const tokenKey = "agent_factory_book_token";
const apiBaseKey = "agent_factory_book_api_base";

function getToken() {
  return localStorage.getItem(tokenKey) || "";
}

function setToken(token) {
  localStorage.setItem(tokenKey, token);
}

function clearToken() {
  localStorage.removeItem(tokenKey);
}

function getApiBase() {
  return localStorage.getItem(apiBaseKey) || "http://127.0.0.1:8000";
}

function setApiBase(url) {
  localStorage.setItem(apiBaseKey, url);
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${getApiBase().replace(/\/$/, "")}${path}`, {
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }
  return data;
}

function fillJson(el, value) {
  if (!el) return;
  el.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

navLinks.forEach((link) => {
  const href = link.getAttribute("href");
  if (href === currentPath) link.classList.add("active");
  link.addEventListener("click", () => {
    document.body.classList.remove("sidebar-open");
    menuToggle?.classList.remove("is-open");
    menuToggle?.setAttribute("aria-expanded", "false");
  });
});

if (menuToggle && sidebar) {
  menuToggle.addEventListener("click", () => {
    const isOpen = document.body.classList.toggle("sidebar-open");
    menuToggle.classList.toggle("is-open", isOpen);
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });
}

if (revealItems.length) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.14, rootMargin: "0px 0px -40px 0px" });

  revealItems.forEach((item) => revealObserver.observe(item));
}

async function loadSessionUI() {
  const meEl = document.querySelector("#meInfo");
  if (!meEl) return;
  try {
    const me = await apiFetch("/me");
    fillJson(meEl, me);
  } catch {
    fillJson(meEl, "Not logged in.");
  }
}

async function wireAuthForms() {
  const signupForm = document.querySelector("#signupForm");
  const loginForm = document.querySelector("#loginForm");
  const authMessage = document.querySelector("#authMessage");
  const apiBaseInput = document.querySelector("#authApiBase");
  if (apiBaseInput) apiBaseInput.value = getApiBase();

  if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const form = new FormData(signupForm);
        const data = await fetch(`${getApiBase().replace(/\/$/, "")}/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.get("email"),
            password: form.get("password"),
            full_name: form.get("full_name"),
          }),
        }).then((r) => r.json());
        if (data.access_token) setToken(data.access_token);
        if (authMessage) authMessage.textContent = "Signup successful.";
        window.location.href = "dashboard.html";
      } catch (error) {
        if (authMessage) authMessage.textContent = error.message;
      }
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const form = new FormData(loginForm);
        const response = await fetch(`${getApiBase().replace(/\/$/, "")}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Login failed");
        setToken(data.access_token);
        if (authMessage) authMessage.textContent = "Login successful.";
        window.location.href = "dashboard.html";
      } catch (error) {
        if (authMessage) authMessage.textContent = error.message;
      }
    });
  }

  const saveApiBaseBtn = document.querySelector("#saveApiBase");
  if (saveApiBaseBtn && apiBaseInput) {
    saveApiBaseBtn.addEventListener("click", () => {
      setApiBase(apiBaseInput.value.trim());
      if (authMessage) authMessage.textContent = "API base saved.";
    });
  }
}

async function wireDashboard() {
  const tokenEl = document.querySelector("#tokenStatus");
  const logoutBtn = document.querySelector("#logoutBtn");
  if (!tokenEl) return;
  tokenEl.textContent = getToken() ? "Authenticated" : "Not logged in";
  logoutBtn?.addEventListener("click", () => {
    clearToken();
    window.location.href = "login.html";
  });
  await loadSessionUI();
}

async function wireConnectionsPage() {
  const form = document.querySelector("#connectionForm");
  const list = document.querySelector("#connectionsList");
  const testBtn = document.querySelector("#testConnectionBtn");
  const deleteBtn = document.querySelector("#deleteConnectionBtn");
  const status = document.querySelector("#connectionStatus");
  const connectionId = document.querySelector("#connectionId");
  if (!form || !list) return;

  async function refresh() {
    const items = await apiFetch("/connections");
    list.innerHTML = items.length
      ? `<ul class="bullet-list">${items.map((item) => `<li>#${item.id} ${item.provider_name} - ${item.base_url}</li>`).join("")}</ul>`
      : "<p class='muted'>No connections yet.</p>";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const data = await apiFetch("/connections", {
        method: "POST",
        body: JSON.stringify({
          provider_name: form.provider_name.value,
          auth_type: form.auth_type.value,
          base_url: form.base_url.value,
          api_key_or_token: form.api_key_or_token.value,
          default_headers: form.default_headers.value ? JSON.parse(form.default_headers.value) : {},
        }),
      });
      if (status) status.textContent = `Created connection #${data.id}`;
      await refresh();
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  testBtn?.addEventListener("click", async () => {
    try {
      const data = await apiFetch(`/connections/${connectionId.value}/test`, { method: "POST", body: "{}" });
      if (status) status.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  deleteBtn?.addEventListener("click", async () => {
    try {
      await apiFetch(`/connections/${connectionId.value}`, { method: "DELETE" });
      if (status) status.textContent = "Deleted";
      await refresh();
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  await refresh();
}

async function wireToolsPage() {
  const form = document.querySelector("#toolForm");
  const list = document.querySelector("#toolsList");
  const testBtn = document.querySelector("#testToolBtn");
  const deleteBtn = document.querySelector("#deleteToolBtn");
  const status = document.querySelector("#toolStatus");
  const toolId = document.querySelector("#toolId");
  if (!form || !list) return;

  async function refresh() {
    const items = await apiFetch("/tools");
    list.innerHTML = items.length
      ? `<ul class="bullet-list">${items.map((item) => `<li>#${item.id} ${item.tool_name} (${item.safety_level})</li>`).join("")}</ul>`
      : "<p class='muted'>No tools yet.</p>";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const data = await apiFetch("/tools", {
        method: "POST",
        body: JSON.stringify({
          connection_id: Number(form.connection_id.value),
          tool_name: form.tool_name.value,
          description: form.description.value,
          method: form.method.value,
          endpoint: form.endpoint.value,
          request_schema: form.request_schema.value ? JSON.parse(form.request_schema.value) : {},
          response_schema: form.response_schema.value ? JSON.parse(form.response_schema.value) : {},
          safety_level: form.safety_level.value,
        }),
      });
      if (status) status.textContent = `Created tool #${data.id}`;
      await refresh();
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  testBtn?.addEventListener("click", async () => {
    try {
      const data = await apiFetch(`/tools/${toolId.value}/test`, {
        method: "POST",
        body: JSON.stringify({ payload: {} }),
      });
      if (status) status.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  deleteBtn?.addEventListener("click", async () => {
    try {
      await apiFetch(`/tools/${toolId.value}`, { method: "DELETE" });
      if (status) status.textContent = "Deleted";
      await refresh();
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  });

  await refresh();
}

async function wireAgentPage() {
  const form = document.querySelector("#agentForm");
  const answer = document.querySelector("#agentAnswer");
  const sources = document.querySelector("#agentSources");
  const status = document.querySelector("#agentStatus");
  if (!form || !answer) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.textContent = "Thinking...";
    try {
      const data = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({
          question: form.question.value,
          mode: form.mode.value,
          chapter: form.chapter.value || null,
          tool_hint: form.tool_hint.value || null,
          confirm: form.confirm.checked,
        }),
      });
      answer.textContent = data.answer;
      sources.textContent = JSON.stringify(data.sources || [], null, 2);
      status.textContent = data.requires_confirmation ? "Confirmation required" : "Done";
    } catch (error) {
      status.textContent = error.message;
    }
  });
}

if (currentPath === "login.html" || currentPath === "signup.html") {
  wireAuthForms();
}
if (currentPath === "dashboard.html") {
  wireDashboard();
}
if (currentPath === "connections.html") {
  wireConnectionsPage();
}
if (currentPath === "tools.html") {
  wireToolsPage();
}
if (currentPath === "agent.html" || currentPath === "chat.html") {
  wireAgentPage();
}

