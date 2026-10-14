const statusEl = document.getElementById("api-status");

api.health()
  .then(() => { statusEl.textContent = "API connected"; })
  .catch(() => { statusEl.textContent = "API offline. Start the backend on port 8000."; });

document.getElementById("analyze-btn").addEventListener("click", async () => {
  const file = document.getElementById("resume-file").files[0];
  const results = document.getElementById("results");
  const body = document.getElementById("results-body");
  results.hidden = false;

  if (!file) {
    body.textContent = "Choose a resume file first.";
    return;
  }
  try {
    const data = await api.uploadResume(file);
    body.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    body.textContent = err.message;
  }
});
