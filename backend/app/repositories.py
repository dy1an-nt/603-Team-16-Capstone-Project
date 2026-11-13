"""Data layer: one repository per table (report section 9).

All SQL lives here and is parameterized (NFR-12). Routers never write queries.

Ownership (NFR-9) is enforced in the SQL itself. Every lookup, update, and
delete of a user's record takes `user_id` and returns None or False when the
record is missing or belongs to someone else. Routers turn both into 404.

Repositories never commit. The connection from `db.get_db` commits when the
request succeeds and rolls back when it raises.

JSONB arguments take plain JSON-ready values, e.g. `issue.model_dump()`.
"""

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb


class EmailTaken(Exception):
    pass


class UserRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create(self, email: str, password_hash: str) -> int:
        """Raises EmailTaken if the email is already registered."""
        # A savepoint, so a duplicate email does not abort the caller's transaction.
        # Not conn.transaction(): as a connection's first statement it commits on exit.
        self.conn.execute("SAVEPOINT create_user")
        try:
            row = self.conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (_normalize_email(email), password_hash),
            ).fetchone()
        except UniqueViolation as e:
            self.conn.execute("ROLLBACK TO SAVEPOINT create_user")
            # No email in the message, so a logged traceback carries no personal data.
            raise EmailTaken from e
        self.conn.execute("RELEASE SAVEPOINT create_user")
        return row["id"]

    def get(self, user_id: int) -> dict | None:
        """Shaped like schemas.UserOut."""
        return self.conn.execute(
            "SELECT id, email, created_at FROM users WHERE id = %s", (user_id,)
        ).fetchone()

    def get_by_email(self, email: str) -> dict | None:
        """Includes password_hash, for login only. Never return this row to a client."""
        return self.conn.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
            (_normalize_email(email),),
        ).fetchone()

    def delete(self, user_id: int) -> bool:
        """Deletes the user and, by cascade, all of their data (FR-3, NFR-14)."""
        cur = self.conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount == 1


class ResumeRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create(
        self,
        user_id: int,
        filename: str | None,
        raw_text: str,
        sections: dict[str, str],
        parsing_metadata: dict | None = None,
    ) -> int:
        row = self.conn.execute(
            "INSERT INTO resumes "
            "(user_id, filename, raw_text, sections, parsing_metadata) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (
                user_id,
                filename,
                raw_text,
                Jsonb(sections),
                Jsonb(parsing_metadata or {}),
            ),
        ).fetchone()
        return row["id"]

    def list_for_user(self, user_id: int) -> list[dict]:
        """Newest first. Each row is shaped like schemas.ResumeSummary."""
        return self.conn.execute(
            "SELECT id, filename, created_at FROM resumes"
            " WHERE user_id = %s ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()

    def get(self, user_id: int, resume_id: int) -> dict | None:
        """Shaped like schemas.ResumeOut, plus raw_text for scoring."""
        return self.conn.execute(
            "SELECT id, filename, raw_text, sections, parsing_metadata, created_at FROM resumes"
            " WHERE id = %s AND user_id = %s",
            (resume_id, user_id),
        ).fetchone()

    def delete(self, user_id: int, resume_id: int) -> bool:
        """Deletes the resume and, by cascade, its job descriptions, analyses, and
        revisions (NFR-14)."""
        cur = self.conn.execute(
            "DELETE FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id)
        )
        return cur.rowcount == 1


class JobDescriptionRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create(self, user_id: int, resume_id: int, raw_text: str, extracted: dict) -> int | None:
        """Returns None if the resume is not this user's.

        `extracted` is a validated schemas.JobRequirements, dumped.
        """
        row = self.conn.execute(
            "INSERT INTO job_descriptions (resume_id, raw_text, extracted)"
            " SELECT r.id, %s, %s FROM resumes r WHERE r.id = %s AND r.user_id = %s"
            " RETURNING id",
            (raw_text, Jsonb(extracted), resume_id, user_id),
        ).fetchone()
        return row["id"] if row else None


class AnalysisRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create(
        self,
        user_id: int,
        resume_id: int,
        ats_score: int,
        issues: list[dict],
        job_description_id: int | None = None,
        match_score: int | None = None,
        keywords: dict | None = None,
    ) -> int | None:
        """Returns None if the resume is not this user's, or the job description
        belongs to a different resume."""
        row = self.conn.execute(
            "INSERT INTO analyses"
            " (resume_id, job_description_id, ats_score, match_score, issues, keywords)"
            " SELECT r.id, %(jd)s, %(ats)s, %(match)s, %(issues)s, %(keywords)s"
            " FROM resumes r WHERE r.id = %(resume)s AND r.user_id = %(user)s"
            " AND (%(jd)s::int IS NULL OR EXISTS ("
            "  SELECT 1 FROM job_descriptions j WHERE j.id = %(jd)s AND j.resume_id = r.id))"
            " RETURNING id",
            {
                "user": user_id,
                "resume": resume_id,
                "jd": job_description_id,
                "ats": ats_score,
                "match": match_score,
                "issues": Jsonb(issues),
                # The column is NOT NULL, so an ATS-only analysis stores {}.
                "keywords": Jsonb(keywords if keywords is not None else {}),
            },
        ).fetchone()
        return row["id"] if row else None

    def get(self, user_id: int, analysis_id: int) -> dict | None:
        """Shaped like schemas.AnalysisOut."""
        row = self.conn.execute(
            "SELECT a.id, a.resume_id, a.job_description_id, a.ats_score, a.issues,"
            " j.extracted AS job_requirements, a.match_score, a.keywords, a.created_at"
            " FROM analyses a"
            " JOIN resumes r ON r.id = a.resume_id"
            " LEFT JOIN job_descriptions j ON j.id = a.job_description_id"
            " WHERE a.id = %s AND r.user_id = %s",
            (analysis_id, user_id),
        ).fetchone()
        if row and row["job_description_id"] is None:
            row["keywords"] = None
        return row


class RevisionRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def create(self, user_id: int, analysis_id: int, suggestions: list[dict]) -> int | None:
        """Returns None if the analysis is not this user's."""
        row = self.conn.execute(
            "INSERT INTO revisions (analysis_id, suggestions)"
            " SELECT a.id, %s FROM analyses a JOIN resumes r ON r.id = a.resume_id"
            " WHERE a.id = %s AND r.user_id = %s RETURNING id",
            (Jsonb(suggestions), analysis_id, user_id),
        ).fetchone()
        return row["id"] if row else None

    def get(self, user_id: int, revision_id: int) -> dict | None:
        """Shaped like schemas.RevisionOut."""
        return self.conn.execute(
            "SELECT v.id, v.analysis_id, v.suggestions, v.revised_text,"
            " a.match_score AS original_match_score, v.new_match_score, v.created_at"
            " FROM revisions v"
            " JOIN analyses a ON a.id = v.analysis_id"
            " JOIN resumes r ON r.id = a.resume_id"
            " WHERE v.id = %s AND r.user_id = %s",
            (revision_id, user_id),
        ).fetchone()

    def update(
        self,
        user_id: int,
        revision_id: int,
        suggestions: list[dict],
        revised_text: str,
        new_match_score: int | None,
    ) -> bool:
        """Saves accept/reject decisions and the re-score (FR-16, FR-17)."""
        cur = self.conn.execute(
            "UPDATE revisions v SET suggestions = %s, revised_text = %s, new_match_score = %s"
            " FROM analyses a JOIN resumes r ON r.id = a.resume_id"
            " WHERE v.id = %s AND a.id = v.analysis_id AND r.user_id = %s",
            (Jsonb(suggestions), revised_text, new_match_score, revision_id, user_id),
        )
        return cur.rowcount == 1


def _normalize_email(email: str) -> str:
    # Case-insensitive, so Ann@x.com and ann@x.com cannot register twice.
    return email.strip().lower()
