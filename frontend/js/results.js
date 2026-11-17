// To handle job analysis and display results


//read job description box
function getJobDescription() {
    const jobInput = document.getElementById("job-text");
    return jobInput.value.trim();
}

//send text from job description box to mock analysis when enabled, otherwise request real analysis
async function requestAnalysis(resumeId, jobDescription = getJobDescription()) {
    if (mockAnalysis.enabled === true) {
        return await mockAnalysis.create(resumeId, jobDescription);
    }
    return await api.createAnalysis(resumeId, jobDescription);
}

//show scores/issues/suggested fixes in results section
function displayAnalysis(analysis) {
    const resultsSection = document.getElementById("results");
    const resultsBody = document.getElementById("results-body");

    resultsBody.replaceChildren();

    const atsScore = document.createElement("h3"); //create heading for ATS /100
    atsScore.textContent = `ATS score: ${analysis.ats_score}/100`;
    resultsBody.append(atsScore);

    if (analysis.match_score !== null) { //if analysis contains job match score, show it 
        const matchScore = document.createElement("h3");
        matchScore.textContent = `Job match score: ${analysis.match_score}/100`;
        resultsBody.append(matchScore);
    }

    const issuesHeading = document.createElement("h3");
    issuesHeading.textContent = "ATS issues";
    resultsBody.append(issuesHeading);

    if (analysis.issues.length === 0) { //if no issues are found
        const message = document.createElement("p");
        message.textContent = "No ATS issues found.";
        resultsBody.append(message);
    } else {
        const issuesList = document.createElement("ul");

        for (const issue of analysis.issues) { //list item for each issue
            const item = document.createElement("li");

            const rule = document.createElement("p");
            rule.textContent = `Rule: ${issue.rule}`;

            const message = document.createElement("p");
            message.textContent = issue.message;

            const fix = document.createElement("p");
            fix.textContent = `Suggested fix: ${issue.fix}`;

            item.append(rule, message, fix);
            issuesList.append(item);
        }

        resultsBody.append(issuesList);
    }

    resultsSection.hidden = false;
}

//get mock analysis results, display them or show error
async function runAnalysis(resumeId, jobDescription = getJobDescription()) {
    const resultsSection = document.getElementById("results");
    const resultsBody = document.getElementById("results-body");

    resultsSection.hidden = false;
    resultsBody.textContent = "Analysing..."; //show while waiting for results

    try {
        const analysis = await requestAnalysis(resumeId, jobDescription);
        displayAnalysis(analysis);
    } catch (error) {
        displayAnalysisError(error, resumeId, jobDescription);
    }
}

// display analysis errors and recovery options for a 502 response.
function displayAnalysisError(error, resumeId, jobDescription) {
    const resultsBody = document.getElementById("results-body");
    resultsBody.replaceChildren(); //clear prev results

    const message = document.createElement("p");
    message.textContent = error.message;
    resultsBody.append(message);

    if (error.status === 502) { //show recovery button only for this error
        const retryButton = document.createElement("button");
        retryButton.type = "button";
        retryButton.textContent = "Retry";

        retryButton.addEventListener("click", () => {
            const currentResumeId = window.currentResumeId;

            if (currentResumeId === null) {
                resultsBody.textContent = "Upload a resume first.";
                return;
            }

            runAnalysis(currentResumeId, jobDescription);
        });

        const atsOnlyButton = document.createElement("button");
        atsOnlyButton.type = "button";
        atsOnlyButton.textContent = "ATS score only"; //only ATS
        atsOnlyButton.style.marginLeft = "8px";

        atsOnlyButton.addEventListener("click", () => {
            const currentResumeId = window.currentResumeId;

            if (currentResumeId === null) {
                resultsBody.textContent = "Upload a resume first.";
                return;
            }

            runAnalysis(currentResumeId, "");
        });

        resultsBody.append(retryButton, atsOnlyButton);
    }
}

// once a resume has been uploaded, enable analysis
function updateAnalysisControls() {
    const hasResume = Number.isInteger(window.currentResumeId);
    const jobInput = document.getElementById("job-text");
    const analyzeButton = document.getElementById("analyze-btn");
    const analysisHelp = document.getElementById("analysis-help");

    jobInput.disabled = !hasResume;
    analyzeButton.disabled = !hasResume;

    analysisHelp.textContent = hasResume
        ? "Paste a job description for matching, or leave it blank for ATS-only analysis."
        : "Upload a resume first to enable analysis.";

    if (!hasResume) {
        jobInput.value = ""; //empty the box when there is no current resume/choosing a new file/logging out
        document.getElementById("results").hidden = true;
    }
}

// update analysis controls when the resume section is shown or hidden
const resumeStateObserver = new MutationObserver(updateAnalysisControls);

resumeStateObserver.observe(document.getElementById("parsed-resume"), {
    attributes: true,
    attributeFilter: ["hidden"],
});

updateAnalysisControls();


//run analysis using the currently uploaded resume
document.getElementById("analyze-btn").addEventListener("click", () => {
    const resumeId = window.currentResumeId;

    if (resumeId === null) {
        document.getElementById("results").hidden = false;
        document.getElementById("results-body").textContent = "Upload a resume first.";
        return;
    }

    runAnalysis(resumeId);
});