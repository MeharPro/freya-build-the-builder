"""The practice harness must keep useful evidence when a case stalls."""
import threading
import unittest
from unittest.mock import patch

from builder import sim


class SimReliabilityTests(unittest.TestCase):
    def test_fast_case_is_persisted_before_slow_first_case(self):
        release_slow = threading.Event()
        fast_saved = threading.Event()
        snapshots = []

        def work(case):
            if case == "slow":
                self.assertTrue(release_slow.wait(2))
            return {"id": case}

        def save(rows):
            snapshots.append([row["id"] for row in rows])
            if snapshots[-1] == ["fast"]:
                fast_saved.set()
                release_slow.set()

        try:
            rows = sim.completed_rows(["slow", "fast"], work, 2, save)
        finally:
            release_slow.set()
        self.assertTrue(fast_saved.is_set())
        self.assertEqual(snapshots[0], ["fast"])
        self.assertEqual([row["id"] for row in rows], ["slow", "fast"])

    def test_published_version_uses_live_version_not_newer_draft(self):
        versions = {"versions": [
            {"id": "live", "versionNumber": 3, "isPublished": True},
            {"id": "draft", "versionNumber": 4, "isPublished": False},
        ]}
        with patch.object(sim.freya, "workspace_id", return_value="ws"), \
             patch.object(sim.freya, "api", return_value=versions) as api:
            self.assertEqual(sim.published_version("workflow"), {"id": "live", "number": 3})
        api.assert_called_once_with("GET", "/api/v2/versions/workflow/workflow", workspaceId="ws")


if __name__ == "__main__":
    unittest.main()
