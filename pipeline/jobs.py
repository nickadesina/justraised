"""Track the talent network's nightly snapshots of currently open postings."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile


def _published_on(value: str | None, today: date) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        published = (timestamp.astimezone(UTC) if timestamp.tzinfo else timestamp).date()
    except ValueError:
        return None
    return published.isoformat() if published <= today else None


class JobHistory:
    def __init__(self, companies: dict | None = None):
        self.companies = companies if companies is not None else {}
        self.live: dict[str, tuple[date, bool, dict[str, str | None]]] = {}

    @classmethod
    def load(cls, path: Path) -> JobHistory:
        return cls(json.loads(path.read_text()) if path.exists() else {})

    def save(self, path: Path) -> None:
        if not self.companies:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
            temp = Path(output.name)
        try:
            temp.write_text(json.dumps(self.companies, sort_keys=True, indent=1) + "\n")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

    def observe(self, slug: str, detail: dict | None, today: date) -> None:
        jobs = (detail or {}).get("jobs")
        if not isinstance(jobs, list):
            self.live.pop(slug, None)
            return

        day = today.isoformat()
        company = self.companies.setdefault(slug, {"snapshots": {}, "jobs": {}})
        live: dict[str, str | None] = {}
        identified = True
        for job in jobs:
            job_id = job.get("id") if isinstance(job, dict) else None
            if not isinstance(job_id, str) or not job_id:
                identified = False
                continue
            published = _published_on(job.get("published_at"), today)
            if published or job_id not in live:
                live[job_id] = published
            entry = company["jobs"].get(job_id)
            if entry is None:
                company["jobs"][job_id] = {
                    "published_on": published, "first_observed": day, "last_observed": day,
                }
            else:
                # A reopened role can have a new posted date but the same ID.
                if published and published <= entry["first_observed"]:
                    prior = entry["published_on"]
                    entry["published_on"] = min(prior, published) if prior else published
                entry["first_observed"] = min(entry["first_observed"], day)
                entry["last_observed"] = max(entry["last_observed"], day)
        # An anonymous posting can disappear before a same-day retry. A later
        # complete list restores the live count but cannot identify that posting.
        snapshots = company["snapshots"]
        snapshots[day] = snapshots.get(day, True) and identified
        self.live[slug] = (today, identified, live)

    def since(self, slug: str, signal: date, today: date) -> dict:
        """Return live counts and distinct observed postings against the same event."""
        company = self.companies.get(slug, {})
        snapshots = company.get("snapshots", {})
        start, end = signal.isoformat(), today.isoformat()
        observed_days = [day for day in snapshots if day <= end]
        stats = {
            "current_postings": None,
            "first_current_post": None,
            "observed_postings_since_signal": None,
            "hiring_tracked_since": min(observed_days, default=None),
            "hiring_coverage": "unavailable",
        }
        snapshot = self.live.get(slug)
        if snapshot is None or snapshot[0] != today:
            return stats

        _, identified, live = snapshot
        if identified and all(live.values()):
            current = [day for day in live.values() if day >= start]
            stats["current_postings"] = len(current)
            stats["first_current_post"] = min(current, default=None)

        known = [job for job in company["jobs"].values() if job["first_observed"] <= end]
        stats["observed_postings_since_signal"] = sum(
            1 for job in known if job["published_on"] and start <= job["published_on"] <= end
        )
        all_days = all(
            snapshots.get((signal + timedelta(days=offset)).isoformat())
            for offset in range((today - signal).days + 1)
        )
        # An undated job already observed before the signal could not have
        # first appeared after it. Other undated jobs make the count a lower bound.
        all_dated = all(job["published_on"] or job["first_observed"] < start for job in known)
        stats["hiring_coverage"] = "since_signal" if all_days and all_dated else "partial"
        return stats
