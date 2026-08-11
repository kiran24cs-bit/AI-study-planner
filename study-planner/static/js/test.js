/* Exam interface: question navigation, palette, timer, auto-submit, results. */

const shell = document.querySelector(".exam-shell");
const testId = Number(shell.dataset.testId);
let questions = [];
let index = 0;
const answers = {};
const visited = new Set();
const timings = {};
let questionStart = Date.now();
let secondsLeft = Number(shell.dataset.duration) * 60;

async function loadTest() {
  const data = await apiGet(`/api/test/${testId}`);
  questions = data.questions;
  renderPalette();
  renderQuestion();
  startTimer();
}

function renderQuestion() {
  const question = questions[index];
  if (!question) return;
  visited.add(question.id);

  document.getElementById("question-area").innerHTML = `
    <div class="q-text">Q${index + 1}. ${esc(question.text)}
      <span class="task-type">${question.difficulty}</span></div>
    ${["A", "B", "C", "D"]
      .map(
        (key) => `<div class="option ${answers[question.id] === key ? "selected" : ""}" data-option="${key}">
          <b>${key}.</b><span>${esc(question.options[key])}</span></div>`
      )
      .join("")}`;

  document.querySelectorAll(".option").forEach((option) =>
    option.addEventListener("click", () => {
      answers[question.id] = option.dataset.option;
      renderQuestion();
      renderPalette();
      updateProgress();
    })
  );

  document.getElementById("prev-q").disabled = index === 0;
  document.getElementById("next-q").textContent = index === questions.length - 1 ? "Review" : "Next";
  renderPalette();
  updateProgress();
}

function renderPalette() {
  document.getElementById("palette").innerHTML = questions
    .map((q, i) => {
      const state = answers[q.id] ? "answered" : visited.has(q.id) ? "visited" : "";
      return `<button class="${state} ${i === index ? "current" : ""}" data-jump="${i}">${i + 1}</button>`;
    })
    .join("");

  document.querySelectorAll("[data-jump]").forEach((btn) =>
    btn.addEventListener("click", () => { recordTime(); index = Number(btn.dataset.jump); renderQuestion(); })
  );
}

function updateProgress() {
  const answered = Object.keys(answers).length;
  document.getElementById("progress-fill").style.width = `${(answered / questions.length) * 100}%`;
}

function recordTime() {
  const question = questions[index];
  if (!question) return;
  const seconds = Math.round((Date.now() - questionStart) / 1000);
  timings[question.id] = (timings[question.id] || 0) + seconds;
  questionStart = Date.now();
}

function startTimer() {
  const display = document.getElementById("exam-timer");
  setInterval(() => {
    secondsLeft -= 1;
    if (secondsLeft <= 0) { submitTest(true); return; }
    const m = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
    const s = String(secondsLeft % 60).padStart(2, "0");
    display.textContent = `${m}:${s}`;
  }, 1000);
}

async function submitTest(auto = false) {
  if (!auto && !confirm("Submit your test now?")) return;
  recordTime();
  try {
    const result = await apiSend("/submit-test", { test_id: testId, answers, timings });
    const score = result.score;
    document.getElementById("result-body").innerHTML = `
      <div class="stat-grid">
        <div class="glass stat"><span class="stat-label">Score</span><strong>${score.percentage}</strong><span class="muted">out of 100</span></div>
        <div class="glass stat"><span class="stat-label">Correct</span><strong>${score.correct}</strong><span class="muted">of ${score.total}</span></div>
        <div class="glass stat"><span class="stat-label">Wrong</span><strong>${score.wrong}</strong><span class="muted">skipped ${score.skipped}</span></div>
        <div class="glass stat"><span class="stat-label">Accuracy</span><strong>${score.accuracy}%</strong><span class="muted">${score.speed}s / question</span></div>
      </div>
      <p class="muted" style="margin-top:14px">${esc(result.adaptation)}</p>`;
    document.getElementById("analysis-link").href = result.analysis_url;
    document.getElementById("result-modal").removeAttribute("hidden");
  } catch (error) {
    toast(error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadTest();
  document.getElementById("next-q").addEventListener("click", () => {
    recordTime();
    if (index < questions.length - 1) { index += 1; renderQuestion(); } else { submitTest(); }
  });
  document.getElementById("prev-q").addEventListener("click", () => {
    recordTime();
    if (index > 0) { index -= 1; renderQuestion(); }
  });
  document.getElementById("clear-q").addEventListener("click", () => {
    delete answers[questions[index].id];
    renderQuestion();
  });
  document.getElementById("submit-test").addEventListener("click", () => submitTest());
});
