/* Dashboard widgets: stats, ring, lists, AI suggestions, Pomodoro timer. */

let chapterForTest = null;

async function loadDashboard() {
  try {
    const data = await apiGet("/api/dashboard");

    document.getElementById("streak").textContent = data.streak;
    document.getElementById("productivity").textContent = data.productivity;
    document.getElementById("minutes-today").textContent = `${data.minutes_today}m`;

    if (data.countdown) {
      document.getElementById("countdown-days").textContent = data.countdown.days;
      document.getElementById("countdown-subject").textContent =
        `${data.countdown.subject} · ${data.countdown.date}`;
    }

    // Progress ring (circumference of r=52 is ~327).
    const ring = document.getElementById("ring-fg");
    ring.style.strokeDashoffset = String(327 - (327 * data.completion) / 100);
    document.getElementById("ring-label").textContent = `${data.completion}%`;

    renderTasks("today-tasks", data.today_tasks, "Nothing scheduled today.");
    renderTasks("revision-list", data.revision_today, "No revision today.");

    document.getElementById("exam-list").innerHTML =
      data.upcoming_exams.length
        ? data.upcoming_exams
            .map(
              (e) => `<div class="data-item"><div class="task-main"><strong>${esc(e.subject_name)}</strong>
              <span class="task-meta">${e.exam_date} · ${prettyTime(e.exam_time)}</span></div></div>`
            )
            .join("")
        : `<p class="muted">No exams added yet.</p>`;

    document.getElementById("weak-topics").innerHTML =
      data.weak_topics.length
        ? data.weak_topics
            .map((w) => `<span class="chip warn">${esc(w.topic)} · ${Math.round(w.score)}%</span>`)
            .join("")
        : `<span class="muted">No weak topics yet.</span>`;
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderTasks(containerId, tasks, emptyText) {
  const container = document.getElementById(containerId);
  if (!tasks.length) {
    container.innerHTML = `<p class="muted">${emptyText}</p>`;
    return;
  }
  container.innerHTML = tasks
    .map(
      (t) => `<div class="task-item ${t.status === "completed" ? "completed" : ""}">
        <span class="task-time">${prettyTime(t.start_time)}</span>
        <div class="task-main"><strong>${esc(t.chapter_name)}</strong>
          <span class="task-meta">${esc(t.subject_name)} · ${t.task_type} · ${t.duration_minutes}m</span></div>
        ${t.status === "completed" ? "" : `<button class="btn ghost sm" data-done="${t.id}" data-chapter="${t.chapter_id || ""}">Done</button>`}
      </div>`
    )
    .join("");

  container.querySelectorAll("[data-done]").forEach((btn) =>
    btn.addEventListener("click", () => completeTask(btn.dataset.done, btn.dataset.chapter))
  );
}

async function completeTask(taskId, chapterId) {
  try {
    const result = await apiSend("/mark-complete", {
      task_id: Number(taskId),
      complete_chapter: Boolean(chapterId),
    });
    toast("Task completed 🎉", "success");
    if (result.offer_test && result.chapter_id) {
      chapterForTest = result.chapter_id;
      document.getElementById("test-modal").removeAttribute("hidden");
    }
    loadDashboard();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadSuggestions() {
  try {
    const data = await apiGet("/api/suggestions");
    document.getElementById("motivation").textContent = data.motivation;
    document.getElementById("suggestions").innerHTML = data.suggestions
      .map((s) => `<li>${esc(s)}</li>`)
      .join("");
  } catch {
    document.getElementById("suggestions").innerHTML = `<li class="muted">Suggestions unavailable.</li>`;
  }
}

/* ------------------------------ Pomodoro ------------------------------ */
const Timer = {
  work: 25,
  rest: 5,
  remaining: 25 * 60,
  onBreak: false,
  handle: null,

  render() {
    const m = String(Math.floor(this.remaining / 60)).padStart(2, "0");
    const s = String(this.remaining % 60).padStart(2, "0");
    document.getElementById("timer-display").textContent = `${m}:${s}`;
  },

  toggle() {
    const button = document.getElementById("timer-start");
    if (this.handle) {
      clearInterval(this.handle);
      this.handle = null;
      button.textContent = "Start";
      return;
    }
    button.textContent = "Pause";
    this.handle = setInterval(() => {
      this.remaining -= 1;
      if (this.remaining <= 0) this.finishPhase();
      this.render();
    }, 1000);
  },

  async finishPhase() {
    clearInterval(this.handle);
    this.handle = null;
    document.getElementById("timer-start").textContent = "Start";

    if (!this.onBreak) {
      Reminders.notify("Focus session complete", "Take a short break.");
      try {
        await apiSend("/api/session", { minutes: this.work, mode: "pomodoro" });
      } catch { /* offline is fine */ }
      this.onBreak = true;
      this.remaining = this.rest * 60;
    } else {
      Reminders.notify("Break over", "Back to studying!");
      this.onBreak = false;
      this.remaining = this.work * 60;
    }
    loadStats();
    loadDashboard();
  },

  reset() {
    clearInterval(this.handle);
    this.handle = null;
    this.onBreak = false;
    this.remaining = this.work * 60;
    document.getElementById("timer-start").textContent = "Start";
    this.render();
  },
};

async function loadStats() {
  try {
    const stats = await apiGet("/api/timer-stats");
    document.getElementById("timer-stats").textContent =
      `${stats.today_minutes}m today · ${stats.total_sessions} sessions · ${stats.total_minutes}m lifetime`;
  } catch { /* ignore */ }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  loadSuggestions();
  loadStats();
  Timer.render();
  Reminders.enable();

  document.getElementById("timer-start").addEventListener("click", () => Timer.toggle());
  document.getElementById("timer-reset").addEventListener("click", () => Timer.reset());

  document.querySelectorAll(".timer-modes .chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      document.querySelectorAll(".timer-modes .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      let work = Number(chip.dataset.work);
      let rest = Number(chip.dataset.break);
      if (chip.textContent.includes("Custom")) {
        const input = prompt("Custom focus minutes?", "40");
        if (input && Number(input) > 0) { work = Number(input); rest = Math.max(3, Math.round(work / 5)); }
      }
      Timer.work = work;
      Timer.rest = rest;
      Timer.reset();
    })
  );

  document.getElementById("take-test").addEventListener("click", async () => {
    if (!chapterForTest) return;
    toast("Generating your test…");
    try {
      const result = await apiSend("/generate-test", { chapter_id: chapterForTest, count: 20 });
      window.location.href = result.url;
    } catch (error) {
      toast(error.message, "error");
    }
  });
});
