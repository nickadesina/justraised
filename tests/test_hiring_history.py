from datetime import date, timedelta

from pipeline.jobs import JobHistory


def test_closed_and_reopened_job_is_one_observed_posting(tmp_path):
    path = tmp_path / "jobs.json"
    start = date(2026, 11, 1)
    history = JobHistory.load(path)
    first = {"id": "A", "published_at": start.isoformat()}
    second = {"id": "B", "published_at": (start + timedelta(days=1)).isoformat()}

    history.observe("town", {"jobs": [first, first]}, start)
    history.save(path)
    history = JobHistory.load(path)
    day_two = start + timedelta(days=1)
    history.observe("town", {"jobs": [second]}, day_two)
    history.observe("town", {"jobs": [second]}, day_two)
    stats = history.since("town", start, day_two)
    assert stats["current_postings"] == 1
    assert stats["observed_postings_since_signal"] == 2
    assert stats["hiring_coverage"] == "since_signal"

    day_three = day_two + timedelta(days=1)
    history.observe("town", {"jobs": [{"id": "A", "published_at": day_three.isoformat()}]}, day_three)
    stats = history.since("town", start, day_three)
    assert stats["current_postings"] == 1
    assert stats["observed_postings_since_signal"] == 2
    since_day_two = history.since("town", day_two, day_three)
    assert since_day_two["current_postings"] == 1  # A is live with a new posted date.
    assert since_day_two["observed_postings_since_signal"] == 1  # Only B was a new ID.
    assert history.companies["town"]["jobs"]["A"] == {
        "published_on": start.isoformat(), "first_observed": start.isoformat(), "last_observed": day_three.isoformat(),
    }


def test_history_respects_missing_detail_gaps_and_late_tracking():
    start = date(2026, 11, 1)
    middle, end = start + timedelta(days=1), start + timedelta(days=2)
    history = JobHistory()
    history.observe("town", {"jobs": []}, start)
    history.observe("town", None, middle)
    missing = history.since("town", start, middle)
    assert missing["hiring_coverage"] == "unavailable"
    assert missing["current_postings"] is None and missing["observed_postings_since_signal"] is None
    assert missing["hiring_tracked_since"] == start.isoformat()

    history.observe("town", {"jobs": []}, end)
    resumed = history.since("town", start, end)
    assert resumed["hiring_coverage"] == "partial"
    assert resumed["observed_postings_since_signal"] == 0
    assert resumed["current_postings"] == 0
    assert history.since("town", end, end)["hiring_coverage"] == "since_signal"
    assert history.since("town", start - timedelta(days=1), end)["hiring_coverage"] == "partial"


def test_unidentifiable_and_undated_postings_leave_coverage_partial():
    start = date(2026, 11, 1)
    history = JobHistory()
    for jobs in ([{"id": "B", "published_at": None}], [{"published_at": "2026-11-01"}]):
        history.observe("town", {"jobs": jobs}, start)
        stats = history.since("town", start, start)
        assert stats["hiring_coverage"] == "partial"
        assert stats["current_postings"] is None
        assert stats["observed_postings_since_signal"] == 0
    history.observe("town", {"jobs": []}, start)
    retry = history.since("town", start, start)
    assert retry["current_postings"] == 0 and retry["hiring_coverage"] == "partial"
    history.observe("town", {}, start)
    assert history.since("town", start, start)["hiring_coverage"] == "unavailable"
