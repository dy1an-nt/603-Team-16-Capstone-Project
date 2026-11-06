// Sample POST /analyses responses for building the results UI before the
// backend endpoint exists. Shapes follow docs/api-contract.md. Remove this
// file once POST /analyses is implemented.
//
// To use it, load it after api.js in index.html:
//   <script src="js/mock-analysis.js"></script>
// then call mockAnalysis.create(resumeId, jobDescription) where the real
// api call will go. Set `enabled` to false (the default) to skip the mock.

const mockAnalysis = {
  enabled: false,
  // Set to true to test the NFR-4 retry and ATS-only fallback.
  failWithJobDescription: false,
  delayMs: 600,

  withJobDescription: {
    id: 31,
    resume_id: 12,
    job_description_id: 18,
    ats_score: 85,
    issues: [
      {
        rule: "missing_projects",
        message: "No 'Projects' section found.",
        fix: "Add a section with the standard heading 'Projects'.",
        penalty: 15,
      },
    ],
    job_requirements: {
      job_title: "Junior Backend Engineer",
      required_skills: ["Python", "PostgreSQL", "Docker"],
      preferred_skills: ["AWS"],
      responsibilities: [],
    },
    match_score: 33,
    keywords: {
      matched: ["Python", "PostgreSQL"],
      missing: ["Docker", "AWS"],
    },
    created_at: "2026-10-14T18:07:22Z",
  },

  atsOnly: {
    id: 32,
    resume_id: 12,
    job_description_id: null,
    ats_score: 70,
    issues: [
      {
        rule: "missing_projects",
        message: "No 'Projects' section found.",
        fix: "Add a section with the standard heading 'Projects'.",
        penalty: 15,
      },
      {
        rule: "missing_skills",
        message: "No 'Skills' section found.",
        fix: "Add a section with the standard heading 'Skills'.",
        penalty: 15,
      },
    ],
    job_requirements: null,
    match_score: null,
    keywords: null,
    created_at: "2026-10-14T18:09:05Z",
  },

  // Resolves or rejects like apiRequest in api.js: errors carry the
  // contract's `detail` message and the HTTP status as `error.status`.
  create(resumeId, jobDescription) {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        const hasJob = Boolean(jobDescription && jobDescription.trim());
        if (hasJob && this.failWithJobDescription) {
          const error = new Error("Job description analysis failed. Try again or run an ATS-only analysis.");
          error.status = 502;
          reject(error);
          return;
        }
        const sample = hasJob ? this.withJobDescription : this.atsOnly;
        resolve(structuredClone({ ...sample, resume_id: resumeId }));
      }, this.delayMs);
    });
  },
};
