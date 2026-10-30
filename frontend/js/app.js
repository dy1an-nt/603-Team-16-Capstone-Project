const statusEl = document.getElementById("api-status");

api.health()
  .then(() => { statusEl.textContent = "API connected"; })
  .catch(() => { statusEl.textContent = "API offline. Start the backend on port 8000."; });

// ---------- Account (FR-1 to FR-3) ----------
const authForm = document.getElementById("auth-form");
const emailInput = document.getElementById("auth-email");
const passwordInput = document.getElementById("auth-password");
const accountActions = document.getElementById("account-actions");
const accountStatus = document.getElementById("account-status");

function renderAccount(message) {
  const loggedIn = api.isLoggedIn();
  authForm.hidden = loggedIn;
  accountActions.hidden = !loggedIn;
  accountStatus.textContent = message ?? (loggedIn ? "Logged in." : "Not logged in.");
}

async function runAccountAction(action, successMessage) {
  // Disabled while a request runs, so a double click cannot send it twice.
  const buttons = document.querySelectorAll("#account button");
  buttons.forEach((b) => { b.disabled = true; });
  accountStatus.textContent = "Working...";
  try {
    await action();
    passwordInput.value = "";
    renderAccount(successMessage);
  } catch (err) {
    renderAccount(err.message);
  } finally {
    buttons.forEach((b) => { b.disabled = false; });
  }
}

authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runAccountAction(() => api.login(emailInput.value, passwordInput.value), "Logged in.");
});

document.getElementById("register-btn").addEventListener("click", () => {
  if (!authForm.reportValidity()) return;
  runAccountAction(
    () => api.register(emailInput.value, passwordInput.value),
    "Account created. Log in to continue.",
  );
});

document.getElementById("logout-btn").addEventListener("click", () => {
  runAccountAction(() => api.logout(), "Logged out.");
});

document.getElementById("delete-account-btn").addEventListener("click", () => {
  const ok = confirm("Delete your account and all saved resumes and analyses? This cannot be undone.");
  if (!ok) return;
  runAccountAction(() => api.deleteAccount(), "Account deleted.");
});

renderAccount();

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
    // A 401 drops the token in api.js, so show the logged-out form again.
    if (!api.isLoggedIn()) renderAccount();
  }
});
