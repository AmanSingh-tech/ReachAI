"""
Target and job ingestion from CSV files.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from reachai.models.target import TargetProfile
from reachai.models.job import Job
from reachai.storage.database import Database


class CSVIngestionSkill:
    """Load targets and jobs from CSV files."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def ingest_targets(self, csv_path: str) -> Dict[str, Any]:
        """
        Load targets from CSV file.
        
        Expected columns: name, title, company, linkedin_url, email, source, location, headline
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Statistics about ingestion
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            return {"status": "error", "error": f"File not found: {csv_path}"}

        loaded = 0
        skipped = 0
        errors = []

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"status": "error", "error": "CSV file is empty"}

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                try:
                    # Normalize column names (lowercase, strip spaces)
                    row = {k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in row.items()}

                    name = row.get("name", "").strip()
                    if not name:
                        skipped += 1
                        continue

                    company = row.get("company", "").strip()
                    if not company:
                        skipped += 1
                        continue

                    target = TargetProfile(
                        target_id=f"csv-{row_num}",
                        name=name,
                        title=row.get("title", "").strip(),
                        company=company,
                        linkedin_url=row.get("linkedin_url", "").strip() or None,
                        email=row.get("email", "").strip() or None,
                        source="csv_import",
                        location=row.get("location", "").strip() or None,
                        headline=row.get("headline", "").strip() or None,
                        status="DISCOVERED",
                    )

                    # Save to database
                    self.db.save_target(target.model_dump())
                    loaded += 1

                except Exception as e:
                    errors.append({"row": row_num, "error": str(e)})
                    skipped += 1

        return {
            "status": "success",
            "loaded": loaded,
            "skipped": skipped,
            "errors": errors if errors else None,
        }

    def ingest_jobs(self, csv_path: str) -> Dict[str, Any]:
        """
        Load jobs from CSV file.
        
        Expected columns: title, company, location, url, description, source
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Statistics about ingestion
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            return {"status": "error", "error": f"File not found: {csv_path}"}

        loaded = 0
        skipped = 0
        errors = []

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"status": "error", "error": "CSV file is empty"}

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Normalize column names
                    row = {k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in row.items()}

                    title = row.get("title", "").strip()
                    if not title:
                        skipped += 1
                        continue

                    company = row.get("company", "").strip()
                    if not company:
                        skipped += 1
                        continue

                    job = Job(
                        job_id=f"csv-job-{row_num}",
                        title=title,
                        company=company,
                        location=row.get("location", "").strip() or None,
                        url=row.get("url", "").strip() or None,
                        description=row.get("description", "").strip() or None,
                        source="csv_import",
                    )

                    self.db.save_job(job.model_dump())
                    loaded += 1

                except Exception as e:
                    errors.append({"row": row_num, "error": str(e)})
                    skipped += 1

        return {
            "status": "success",
            "loaded": loaded,
            "skipped": skipped,
            "errors": errors if errors else None,
        }

    def list_targets(self, status: str | None = None) -> List[Dict[str, Any]]:
        """List all targets, optionally filtered by status."""
        return self.db.list_targets(status=status)

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs."""
        return self.db.list_jobs()
