/* Planner page: monthly calendar, day detail, drag & drop, regeneration. */

let cursor = new Date();
let selected = new Date().toISOString().slice(0, 10);
let planData = { days: {}, exams: {}, unavailable: {} };

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

async function loadMonth() {
  const month = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`;
  document.getElementById("month-label").textContent = `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;
  planData = await apiGet(`/api/planner?month=${month}`);
  renderCalendar();
  renderDay();
}

function renderCalendar() {
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday-first grid
  const total = new Date(year, month + 1, 0).getDate();
  const today = new Date().toISOString().slice(0, 10);

  let html = "";
  for (let i = 0; i < offset; i += 1) html += `<div class="cell empty"></div>`;

  for (let day = 1; day <= total; day += 1) {
    const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const tasks = planData.days[iso] || [];
    const classes = ["cell"];
    if (iso === today) classes.push("today");
    if (iso === selected) classes.push("selected");
    if (planData.exams[iso]) classes.push("exam");
    if (planData.unavailable[iso]) classes.push("blocked");

    const dots = tasks
      .slice(0, 6)
      .map((t) => `<i style="background:${dotColor(t)}"></i>`)
      .join("");

    html += `<div class="${classes.join(" ")}" data-day="${iso}">
      <span class="cell-day">${day}</span>
      ${planData.exams[iso] ? `<span class="cell-tag">Exam</span>` : ""}
      <div class="cell-dots">${dots}</div>
    </div>`;
  }

  const calendar = document.getElementById("calendar");
  calendar.innerHTML = html;

  calendar.querySelectorAll(".cell[data-day]").forEach((cell) => {
    cell.addEventListener("click", () => { selected = cell.dataset.day; renderCalendar(); renderDay(); });
    cell.addEventListener("dragover", (e) => { e.preventDefault(); cell.classList.add("drag-over"); });
    cell.addEventListener("dragleave", () => cell.classList.remove("drag-over"));
    cell.addEventListener("drop", async (e) => {
      e.preventDefault();
      cell.classList.remove("drag-over");
      const taskId = e.dataTransfer.getData("text/plain");
      if (!taskId) return;
      try {
        await apiSend(`/api/tasks/${taskId}`, { day: cell.dataset.day }, "PATCH");
        toast("Task moved.", "success");
        loadMonth();
      } catch (error) {
        toast(error.message, "error");
      }
    });
  });
}

function dotColor(task) {
  if (task.status === "completed") return "var(--green)";
  if (task.task_type === "revision" || task.task_type === "final") return "var(--blue)";
  if (task.task_type === "mock") return "var(--red)";
  return "var(--orange)";
}

function renderDay() {
  const tasks = planData.days[selected] || [];
  document.getElementById("day-title").textContent = `Tasks for ${selected}`;
  const container = document.getElementById("day-tasks");

  if (!tasks.length) {
    container.innerHTML = `<p class="muted">Nothing scheduled. Use “Regenerate selected day”.</p>`;
    return;
  }

  container.innerHTML = tasks
    .map(
      (t) => `<div class="task-item ${t.status === "completed" ? "completed" : ""}" draggable="true" data-id="${t.id}">
        <span class="task-time">${prettyTime(t.start_time)}</span>
        <div class="task-main"><strong>${esc(t.chapter_name)}</strong>
          <span class="task-meta">${esc(t.subject_name)} · ${t.duration_minutes}m</span></div>
        <span class="task-type ${t.task_type}">${t.task_type}</span>
        ${t.status === "completed" ? "" : `<button class="btn ghost sm" data-done="${t.id}" data-chapter="${t.chapter_id || ""}">Done</button>`}
        <button class="icon-btn" data-del="${t.id}" title="Delete">✕</button>
      </div>`
    )
    .join("");

  container.querySelectorAll("[draggable]").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", el.dataset.id);
      el.classList.add("dragging");
    });
    el.addEventListener("dragend", () => el.classList.remove("dragging"));
  });

  container.querySelectorAll("[data-del]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await apiSend(`/api/tasks/${btn.dataset.del}`, null, "DELETE");
      toast("Task deleted.");
      loadMonth();
    })
  );

  container.querySelectorAll("[data-done]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      try {
        const result = await apiSend("/mark-complete", {
          task_id: Number(btn.dataset.done),
          complete_chapter: Boolean(btn.dataset.chapter),
        });
        toast("Marked complete 🎉", "success");
        if (result.offer_test && result.chapter_id) {
          document.getElementById("test-modal").removeAttribute("hidden");
          document.getElementById("take-test").dataset.chapter = result.chapter_id;
        }
        loadMonth();
      } catch (error) {
        toast(error.message, "error");
      }
    })
  );
}

document.addEventListener("DOMContentLoaded", () => {
  loadMonth();

  document.getElementById("prev-month").addEventListener("click", () => {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1); loadMonth();
  });
  document.getElementById("next-month").addEventListener("click", () => {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1); loadMonth();
  });

  document.getElementById("regen-day").addEventListener("click", async () => {
    try {
      const result = await apiSend("/update-plan", { day: selected });
      toast(result.message, "success");
      loadMonth();
    } catch (error) { toast(error.message, "error"); }
  });

  document.getElementById("regen-all").addEventListener("click", async () => {
    if (!confirm("Rebuild the entire timetable? Existing tasks will be replaced.")) return;
    try {
      const result = await apiSend("/generate-plan");
      toast(result.message, "success");
      loadMonth();
    } catch (error) { toast(error.message, "error"); }
  });

  document.getElementById("take-test").addEventListener("click", async (event) => {
    const chapterId = Number(event.target.dataset.chapter);
    if (!chapterId) return;
    toast("Generating your test…");
    try {
      const result = await apiSend("/generate-test", { chapter_id: chapterId, count: 20 });
      window.location.href = result.url;
    } catch (error) { toast(error.message, "error"); }
  });
});
