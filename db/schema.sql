-- Resume Reviewer schema.
-- Load with: psql -U resume -d resume_reviewer -f db/schema.sql
-- All child tables cascade on delete (FR-3, NFR-14).

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS resumes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename   TEXT,
    raw_text   TEXT NOT NULL,
    sections   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Belongs to the resume it was scored against, so deleting the resume removes
-- it too (NFR-14). The owner is resumes.user_id.
CREATE TABLE IF NOT EXISTS job_descriptions (
    id         SERIAL PRIMARY KEY,
    resume_id  INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    raw_text   TEXT NOT NULL,
    extracted  JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analyses (
    id                 SERIAL PRIMARY KEY,
    resume_id          INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    job_description_id INTEGER REFERENCES job_descriptions(id) ON DELETE CASCADE,
    ats_score          INTEGER NOT NULL CHECK (ats_score BETWEEN 0 AND 100),
    match_score        INTEGER CHECK (match_score BETWEEN 0 AND 100),
    issues             JSONB NOT NULL DEFAULT '[]'::jsonb,
    keywords           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revisions (
    id              SERIAL PRIMARY KEY,
    analysis_id     INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    suggestions     JSONB NOT NULL DEFAULT '[]'::jsonb,
    revised_text    TEXT,
    new_match_score INTEGER CHECK (new_match_score BETWEEN 0 AND 100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_jd_resume ON job_descriptions(resume_id);
CREATE INDEX IF NOT EXISTS idx_analyses_resume ON analyses(resume_id);
CREATE INDEX IF NOT EXISTS idx_revisions_analysis ON revisions(analysis_id);
