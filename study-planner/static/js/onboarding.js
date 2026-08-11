/* 5-step setup wizard: timetable, unavailable days, availability, syllabus, generate. */

let step = 1;

function showStep(next) {
  step = Math.min(5, Math.max(1, next));
  document.querySelectorAll(".step").forEach((section) => {
    section.hidden = Number(section.dataset.step) !== step;
  });
  document.querySelectorAll(".wizard-nav li").forEach((li) => {
    li.classList.toggle("active", Number(li.dataset.step) === step);
  });
}

/* ------------------------- Step 1: exams ------------------------- */
async function loadExams() {
  const { exams } = await apiGet("/api/exams");
  document.getElementById("exam-table").innerHTML = exams.length
    ? exams
        .map(
          (e) => `<div class="data-item"><div class="task-main"><strong>${esc(e.subject_name)}</strong>
          <span class="task-meta">${e.exam_date} · ${prettyTime(e.exam_time)} · ${e.duration_minutes}m</span></div>
          <button class="btn ghost sm" data-del-exam="${e.id}">Remove</button></div>`
        )
        .join("")
    : `<p class="muted">No exams yet.</p>`;

  document.querySelectorAll("[data-del-exam]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await apiSend(`/api/exams/${btn.dataset.delExam}`, null, "DELETE");
      loadExams();
    })
  );
}

/* --------------------- Step 2: unavailable days --------------------- */
async function loadOffDays(payload) {
  const data = payload || (await apiGet("/api/unavailable"));
  document.getElementById("off-list").innerHTML = data.days.length
    ? data.days
        .map(
          (d) => `<div class="data-item"><div class="task-main"><strong>${d.day}</strong>
          <span class="task-meta">${esc(d.reason)}</span></div>
          <button class="btn ghost sm" data-del-off="${d.id}">Remove</button></div>`
        )
        .join("")
    : `<p class="muted">No blocked days.</p>`;

  document.querySelectorAll("[data-del-off]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await apiSend(`/api/unavailable/${btn.dataset.delOff}`, null, "DELETE");
      loadOffDays();
    })
  );
}

/* ---------------------- Step 3: availability ---------------------- */
const TIME_FIELDS = ["wake_time","sleep_time","college_start","college_end","work_start","work_end","break_start","break_end","preferred_start"];

async function loadAvailability() {
  const { availability } = await apiGet("/api/availability");
  TIME_FIELDS.forEach((field) => {
    const input = document.getElementById(field);
    if (input && availability[field]) input.value = availability[field];
  });
  document.getElementById("max_daily_hours").value = availability.max_daily_hours;
  document.getElementById("session_minutes").value = availability.session_minutes;
}

/* ------------------------ Step 4: syllabus ------------------------ */
async function loadSyllabus(payload) {
  const data = payload || (await apiGet("/api/syllabus"));
  document.getElementById("syllabus-list").innerHTML = data.subjects.length
    ? data.subjects
        .map(
          (s) => `<div class="data-item" style="flex-direction:column;align-items:stretch">
            <strong>${esc(s.name)} <span class="muted">(${s.chapters.length} chapters)</span></strong>
            ${s.chapters
              .map(
                (c) => `<div class="task-item"><div class="task-main"><strong>${esc(c.name)}</strong>
                <span class="task-meta">${esc(c.unit || "—")} · difficulty ${c.difficulty} · priority ${c.priority} · ${c.estimated_hours}h</span></div>
                <button class="btn ghost sm" data-del-ch="${c.id}">Remove</button></div>`
              )
              .join("")}
          </div>`
        )
        .join("")
    : `<p class="muted">No syllabus yet.</p>`;

  document.querySelectorAll("[data-del-ch]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await apiSend(`/api/chapters/${btn.dataset.delCh}`, null, "DELETE");
      loadSyllabus();
    })
  );
}

/* ----------------------------- Wiring ----------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  showStep(1);
  loadExams();
  loadOffDays();
  loadAvailability();
  loadSyllabus();

  document.getElementById("next-step").addEventListener("click", () => showStep(step + 1));
  document.getElementById("prev-step").addEventListener("click", () => showStep(step - 1));
  document.querySelectorAll(".wizard-nav li").forEach((li) =>
    li.addEventListener("click", () => showStep(Number(li.dataset.step)))
  );

  document.getElementById("timetable-upload").addEventListener("click", async () => {
    const file = document.getElementById("timetable-file").files[0];
    if (!file) return toast("Choose a file first.", "error");
    toast("Reading your timetable…");
    try {
      await apiUpload("/upload-timetable", file);
      toast("Timetable imported.", "success");
      loadExams();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("exam-add").addEventListener("click", async () => {
    const subject = document.getElementById("exam-subject").value.trim();
    const date = document.getElementById("exam-date").value;
    if (!subject || !date) return toast("Subject and date are required.", "error");
    try {
      await apiSend("/upload-timetable", {
        exams: [{
          subject,
          date,
          time: document.getElementById("exam-time").value,
          duration_minutes: Number(document.getElementById("exam-duration").value) || 180,
        }],
      });
      document.getElementById("exam-subject").value = "";
      toast("Exam added.", "success");
      loadExams();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("off-add").addEventListener("click", async () => {
    const day = document.getElementById("off-date").value;
    if (!day) return toast("Pick a date.", "error");
    const data = await apiSend("/api/unavailable", {
      day,
      reason: document.getElementById("off-reason").value || "Unavailable",
    });
    document.getElementById("off-reason").value = "";
    loadOffDays(data);
    toast("Day blocked.", "success");
  });

  document.getElementById("availability-save").addEventListener("click", async () => {
    const payload = {};
    TIME_FIELDS.forEach((f) => { payload[f] = document.getElementById(f).value; });
    payload.max_daily_hours = Number(document.getElementById("max_daily_hours").value);
    payload.session_minutes = Number(document.getElementById("session_minutes").value);
    try {
      await apiSend("/api/availability", payload);
      toast("Routine saved.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("syllabus-upload").addEventListener("click", async () => {
    const file = document.getElementById("syllabus-file").files[0];
    if (!file) return toast("Choose a file first.", "error");
    toast("Reading your syllabus…");
    try {
      const data = await apiUpload("/upload-syllabus", file);
      toast(`Imported ${data.created} chapters.`, "success");
      loadSyllabus();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("ch-add").addEventListener("click", async () => {
    const subject = document.getElementById("ch-subject").value.trim();
    const name = document.getElementById("ch-name").value.trim();
    if (!subject || !name) return toast("Subject and chapter are required.", "error");
    try {
      await apiSend("/upload-syllabus", {
        subjects: [{
          name: subject,
          chapters: [{
            unit: document.getElementById("ch-unit").value,
            name,
            topics: document.getElementById("ch-topics").value,
            difficulty: Number(document.getElementById("ch-difficulty").value),
            estimated_hours: Number(document.getElementById("ch-hours").value),
            priority: Number(document.getElementById("ch-priority").value),
          }],
        }],
      });
      document.getElementById("ch-name").value = "";
      document.getElementById("ch-topics").value = "";
      toast("Chapter added.", "success");
      loadSyllabus();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  document.getElementById("generate-plan").addEventListener("click", async (event) => {
    event.target.disabled = true;
    try {
      const result = await apiSend("/generate-plan");
      document.getElementById("generate-result").textContent = result.message;
      toast(result.message, "success");
      setTimeout(() => { window.location.href = "/planner"; }, 900);
    } catch (error) {
      document.getElementById("generate-result").textContent = error.message;
      toast(error.message, "error");
    } finally {
      event.target.disabled = false;
    }
  });
});
