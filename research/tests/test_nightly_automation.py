"""Guard the overnight result -> archive -> site -> monitoring schedule.

The archived first-pick result ledger must refresh before a nightly Pages build.
These tests intentionally use only stdlib so they run in the existing CI suite.
They validate configuration, not actual GitHub scheduler delivery.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def schedules(filename: str) -> list[str]:
    content = (WORKFLOWS / filename).read_text(encoding="utf-8")
    values = re.findall(r'^\s*- cron: "([^"]+)"', content, re.MULTILINE)
    if not values:
        raise AssertionError(f"{filename} has no scheduled triggers")
    if content.count('timezone: "America/New_York"') < len(values):
        raise AssertionError(f"{filename} must use daylight-saving-aware Eastern crons")
    return values


def times(crons: list[str]) -> set[tuple[int, int]]:
    return {
        (int(hour), int(minute))
        for cron in crons
        for minute_field, hour_field, *_ in [cron.split()]
        for minute in minute_field.split(",")
        for hour in hour_field.split(",")
    }


class NightlyAutomationContract(unittest.TestCase):
    def test_nightly_archive_runs_before_nightly_site_rebuild(self):
        archive = schedules("archive-pregame.yml")
        deploy = schedules("deploy-pages.yml")
        self.assertEqual(archive, ["7 2,6,9,16 * 1,2,3,4,11,12 *"])
        self.assertIn("47 2 * * *", deploy)
        self.assertIn("47 6 * 1,2,3,4,11,12 *", deploy)
        self.assertIn("17 10,17 * 1,2,3,4,11,12 *", deploy)
        archive_times, page_times = times(archive), times(deploy)
        for hour, minute in ((2, 47), (6, 47), (10, 17), (17, 17)):
            self.assertIn((hour, minute), page_times)
            preceding = {(2, 7), (6, 7), (9, 7), (16, 7)}
            self.assertTrue(
                any(0 < 60 * hour + minute - (60 * ah + am) <= 75
                    for ah, am in archive_times & preceding),
                msg=f"Site build {hour:02}:{minute:02} lacks preceding forecast archive",
            )

    def test_archive_triggers_site_and_commits_only_verified_ledger(self):
        archive = (WORKFLOWS / "archive-pregame.yml").read_text(encoding="utf-8")
        deploy = (WORKFLOWS / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("python -m forecast.snapshot", archive)
        self.assertIn("python -m forecast.audit", archive)
        self.assertIn("git add web/public/forecasts", archive)
        self.assertIn('workflows: ["Archive real pre-tipoff forecasts"]', deploy)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", deploy)

    def test_morning_monitor_catches_missing_overnight_settlement(self):
        monitor = (WORKFLOWS / "monitor-archive.yml").read_text(encoding="utf-8")
        self.assertEqual(schedules("monitor-archive.yml"),
                         ["35 7,11,18 * 1,2,3,4,11,12 *"])
        self.assertIn("--require-recent --max-age-hours 6", monitor)
        self.assertIn("if: failure()", monitor)


if __name__ == "__main__":
    unittest.main()
