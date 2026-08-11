/* Powers both the AI Analysis page and the Chart.js Performance page. */

/* ----------------------------- Analysis ----------------------------- */
async function loadAnalysis() {
  const testId = document.querySelector(".app-shell")?.dataset.testId;
  const url = testId ? `/api/analysis/${testId}` : "/api/analysis";
  try {
    const { analysis } = await apiGet(url);
    const score = analysis.score;

    document.getElementById("analysis-title").textContent =
      `${score.subject_name} — ${score.chapter_name}`;

    document.getElementById("analysis-summary").innerHTML = `
      <div class="glass stat"><span class="stat-label">Score</span><strong>${score.percentage}</strong><span class="muted">/100</span></div>
      <div class="glass stat"><span class="stat-label">Accuracy</span><strong>${score.accuracy}%</strong><span class="muted">${score.correct}/${score.total} correct</span></div>
      <div class="glass stat"><span class="stat-label">Speed</span><strong>${score.speed}s</strong><span class="muted">per question</span></div>
      <div class="glass stat"><span class="stat-label">Skipped</span><strong>${score.skipped}</strong><span class="muted">questions</span></div>`;

    const chips = (items, cls) =>
      items.length
        ? items.map((t) => `<span class="chip ${cls}">${esc(t)}</span>`).join("")
        : `<span class="muted">None detected.</span>`;

    document.getElementById("weak").innerHTML = chips(analysis.weak_topics || [], "warn");
    document.getElementById("strong").innerHTML = chips(analysis.strong_topics || [], "");
    document.getElementById("gaps").textContent = analysis.concept_gaps || "—";
    document.getElementById("time").textContent = analysis.time_management || "—";
    document.getElementById("guess").textContent = analysis.guessing_pattern || "—";
    document.getElementById("confidence").textContent = analysis.confidence || "—";

    document.getElementById("mistakes").innerHTML = (analysis.mistakes || []).length
      ? analysis.mistakes
          .map(
            (m) => `<div class="data-item"><div class="task-main"><strong>${esc(m.topic)}</strong>
            <span class="task-meta">chose ${m.chosen || "—"} · correct ${m.correct} · ${m.difficulty} · ${m.seconds}s</span></div></div>`
          )
          .join("")
      : `<p class="muted">No mistakes — perfect run!</p>`;
  } catch (error) {
    document.getElementById("analysis-summary").innerHTML = `<p class="muted">${esc(error.message)}</p>`;
  }
}

/* ---------------------------- Performance ---------------------------- */
const CHART_COLORS = ["#6366f1", "#22d3ee", "#f472b6", "#f59e0b", "#22c55e", "#ef4444"];

function makeChart(id, type, labels, data, label) {
  const canvas = document.getElementById(id);
  if (!canvas || typeof Chart === "undefined") return;
  new Chart(canvas, {
    type,
    data: {
      labels,
      datasets: [{
        label,
        data,
        backgroundColor: type === "line" ? "rgba(99,102,241,.2)" : CHART_COLORS,
        borderColor: "#6366f1",
        borderWidth: 2,
        tension: 0.35,
        fill: type === "line",
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: type === "doughnut" } },
      scales: type === "doughnut" ? {} : { y: { beginAtZero: true } },
    },
  });
}

async function loadPerformance() {
  try {
    const data = await apiGet("/api/performance");

    makeChart("chart-weekly", "bar", data.weekly.map((d) => d.day), data.weekly.map((d) => d.minutes), "Minutes");
    makeChart("chart-monthly", "line", data.monthly.map((d) => d.day), data.monthly.map((d) => d.minutes), "Minutes");
    makeChart("chart-subject", "bar", data.subjects.map((s) => s.name), data.subjects.map((s) => s.avg), "Avg %");
    makeChart("chart-chapter", "bar", data.chapters.map((c) => c.name), data.chapters.map((c) => c.avg), "Avg %");
    makeChart("chart-accuracy", "line", data.accuracy.map((a) => a.date), data.accuracy.map((a) => a.value), "Accuracy %");
    makeChart("chart-weak", "doughnut", data.weak_topics.map((w) => w.topic), data.weak_topics.map((w) => Math.round(100 - w.score)), "Gap");

    document.getElementById("history").innerHTML = data.history.length
      ? data.history
          .reverse()
          .map(
            (s) => `<div class="data-item"><div class="task-main"><strong>${esc(s.chapter_name)}</strong>
            <span class="task-meta">${esc(s.subject_name)} · ${s.created_at.slice(0, 10)} · accuracy ${s.accuracy}%</span></div>
            <strong>${s.percentage}%</strong>
            <a class="btn ghost sm" href="/analysis/${s.test_id}">Analysis</a></div>`
          )
          .join("")
      : `<p class="muted">No tests taken yet.</p>`;
  } catch (error) {
    toast(error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("analysis-summary")) loadAnalysis();
  if (document.getElementById("chart-weekly")) loadPerformance();
});
