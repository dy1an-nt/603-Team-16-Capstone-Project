ALTER TABLE resumes
ADD COLUMN IF NOT EXISTS parsing_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
