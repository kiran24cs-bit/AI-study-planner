/* Settings page: theme, reminders, study hours, reset and exports. */

document.addEventListener("DOMContentLoaded", async () => {
  // ---- Theme ----
  const themeSelect = document.getElementById("theme-select");
  themeSelect.addEventListener("change", async () => {
    applyTheme(themeSelect.value);
    await apiSend("/api/settings", { theme: themeSelect.value });
    toast("Theme saved.", "success");
  });

  // ---- Reminders ----
  try {
    const { reminders } = await apiGet("/api/reminders");
    reminders.forEach((r) => {
      const row = document.querySelector(`.reminder-row[data-kind="${r.kind}"]`);
      if (!row) return;
      row.querySelector('input[type="time"]').value = r.time;
      row.querySelector('input[type="checkbox"]').checked = r.enabled;
    });
    Reminders.start(reminders);
  } catch { /* first run */ }

  document.getElementById("save-reminders").addEventListener("click", async () => {
    await Reminders.enable();
    const rows = [...document.querySelectorAll(".reminder-row")];
    try {
      for (const row of rows) {
        await apiSend("/api/reminders", {
          kind: row.dataset.kind,
          time: row.querySelector('input[type="time"]').value,
          enabled: row.querySelector('input[type="checkbox"]').checked,
        });
      }
      toast("Reminders saved.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });

  // ---- Study hours ----
  try {
    const { availability } = await apiGet("/api/availability");
    document.getElementById("max-hours").value = availability.max_daily_hours;
    document.getElementById("session-length").value = availability.session_minutes;
  } catch { /* ignore */ }

  document.getElementById("save-hours").addEventListener("click", async () => {
    try {
      await apiSend("/api/availability", {
        max_daily_hours: Number(document.getElementById("max-hours").value),
        session_minutes: Number(document.getElementById("session-length").value),
      });
      toast("Study hours saved.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });

  // ---- Reset ----
  document.getElementById("reset-planner").addEventListener("click", async () => {
    if (!confirm("Delete every scheduled task? Your syllabus and exams stay.")) return;
    const result = await apiSend("/api/reset-planner");
    toast(result.message, "success");
  });
});
