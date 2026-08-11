/* ==========================================================================
   Shared front-end helpers: theme, toasts, fetch wrappers, reveal, notifications
   ========================================================================== */

/** Show a transient toast notification. */
function toast(message, type = "info") {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 3600);
}

/** GET JSON with error handling. */
async function apiGet(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

/** Send JSON (POST/PATCH/DELETE) with error handling. */
async function apiSend(url, body = null, method = "POST") {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

/** Upload a file to an endpoint as multipart/form-data. */
async function apiUpload(url, file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(url, { method: "POST", body: form });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Upload failed");
  return data;
}

/** Theme handling — persisted in localStorage. */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("sp-theme", theme);
}

/** Format a "HH:MM" string for display. */
function prettyTime(value) {
  return value || "--:--";
}

/** Escape user/AI text before injecting into HTML. */
function esc(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

/** Ask for notification permission and fire scheduled reminders. */
const Reminders = {
  async enable() {
    if (!("Notification" in window)) return false;
    const permission = await Notification.requestPermission();
    return permission === "granted";
  },
  notify(title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body });
    } else {
      toast(`${title} — ${body}`);
    }
  },
  /** Poll every minute and fire any reminder whose time matches now. */
  start(reminders) {
    const fired = new Set();
    setInterval(() => {
      const now = new Date();
      const stamp = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      reminders
        .filter((r) => r.enabled && r.time === stamp && !fired.has(r.kind + stamp))
        .forEach((r) => {
          fired.add(r.kind + stamp);
          Reminders.notify("StudyPilot", `${r.kind} reminder — time to go!`);
        });
    }, 30000);
  },
};

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(localStorage.getItem("sp-theme") || "dark");

  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: next }),
    }).catch(() => {});
  });

  document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
    document.getElementById("sidebar")?.classList.toggle("open");
  });

  // Reveal-on-scroll animation
  const observer = new IntersectionObserver(
    (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
    { threshold: 0.12 }
  );
  document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

  // Generic modal close
  document.querySelectorAll("[data-close]").forEach((btn) =>
    btn.addEventListener("click", () => btn.closest(".modal").setAttribute("hidden", ""))
  );
});
