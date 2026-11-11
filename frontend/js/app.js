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
  if (!loggedIn) clearParsedResume();
  updateUploadControls();
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

// ---------- Upload and parsed sections (FR-4, FR-7, FR-8) ----------
const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("resume-file");
const uploadButton = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");
const parsedResume = document.getElementById("parsed-resume");
const parsedSections = document.getElementById("parsed-sections");
let uploading = false;
// Invalidate in-flight results when the account changes.
let uploadGeneration = 0;

function clearParsedResume() {
  uploadGeneration += 1;
  parsedResume.hidden = true;
  parsedSections.replaceChildren();
  document.getElementById("resume-filename").textContent = "";
  fileInput.value = "";
}

function updateUploadControls() {
  const loggedIn = api.isLoggedIn();
  fileInput.disabled = uploading || !loggedIn;
  uploadButton.disabled = uploading || !loggedIn;
  uploadButton.textContent = uploading ? "Uploading and parsing..." : "Upload and view sections";
  uploadForm.setAttribute("aria-busy", String(uploading));
  if (!uploading) {
    uploadStatus.textContent = loggedIn ? "Choose a resume to get started." : "Log in to upload a resume.";
    uploadStatus.className = "muted";
  }
}

function renderSections(resume) {
  const labels = {
    contact: "Contact", summary: "Summary", education: "Education",
    experience: "Experience", projects: "Projects", skills: "Skills",
  };
  parsedSections.replaceChildren();
  document.getElementById("resume-filename").textContent = resume.filename || "Uploaded resume";
  for (const [key, label] of Object.entries(labels)) {
    const section = document.createElement("section");
    section.className = "parsed-section";
    const heading = document.createElement("h3");
    heading.textContent = label;
    const text = document.createElement("p");
    const content = resume.sections?.[key];
    text.textContent = typeof content === "string" && content.trim() ? content : "No text detected for this section.";
    text.className = typeof content === "string" && content.trim() ? "section-text" : "muted";
    section.append(heading, text);
    parsedSections.append(section);
  }
  parsedResume.hidden = false;
  document.getElementById("parsed-title").focus();
}

function uploadError(error) {
  switch (error.status) {
    case 413:
      // Keep the configured server limit as the source of truth.
      return `File too large. ${error.message} Choose a smaller PDF or DOCX and try again.`;
    case 415:
      return "Unsupported file type. Choose a PDF (.pdf) or Word document (.docx).";
    case 400:
      return "The resume could not be read. It may be empty, damaged, or an image-only scan. Export a text-based PDF or DOCX and try again.";
    case 401:
      return "Your session has expired. Log in again, then choose your resume to retry.";
    case 501:
      return "Resume upload is not available on this backend yet. Please try again after the backend is updated.";
    default:
      return "Upload failed. Check that the backend is running and try again.";
  }
}

fileInput.addEventListener("change", () => {
  parsedResume.hidden = true;
  parsedSections.replaceChildren();
  uploadStatus.className = "muted";
  uploadStatus.textContent = fileInput.files[0]
    ? `Ready to upload: ${fileInput.files[0].name}`
    : "Choose a resume to get started.";
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (uploading) return;
  if (!api.isLoggedIn()) {
    renderAccount();
    return;
  }
  const file = fileInput.files[0];
  if (!file) {
    uploadStatus.textContent = "Choose a resume file first.";
    return;
  }
  const generation = ++uploadGeneration;
  parsedResume.hidden = true;
  parsedSections.replaceChildren();
  uploading = true;
  updateUploadControls();
  uploadStatus.className = "muted";
  uploadStatus.textContent = "Uploading and extracting resume sections...";
  let message;
  let failed = false;
  try {
    const resume = await api.uploadResume(file);
    if (generation !== uploadGeneration || !api.isLoggedIn()) return;
    renderSections(resume);
    message = "Resume uploaded and saved. Review the parsed sections below.";
  } catch (error) {
    if (generation !== uploadGeneration) return;
    failed = true;
    message = uploadError(error);
    if (!api.isLoggedIn()) renderAccount();
  } finally {
    uploading = false;
    updateUploadControls();
    if (message) {
      uploadStatus.textContent = message;
      uploadStatus.className = failed ? "error-message" : "success-message";
    }
  }
});

renderAccount();
