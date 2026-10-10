"""Regressions for observed asynchronous Freya simulation status drift."""
import unittest
from unittest.mock import patch

import freya


class SimulationPollingTests(unittest.TestCase):
    def test_completed_iteration_finishes_even_when_parent_is_running(self):
        replies = [
            {"simulation": {"id": "sim"}},
            {"simulation": {"status": "running"}},
            {"iterations": [{"id": "iteration", "status": "completed"}]},
        ]
        with patch.object(freya, "api", side_effect=replies) as api, \
                patch.object(freya.time, "sleep"):
            self.assertEqual(freya.run_simulation("agent", "test", {"persona": {}}),
                             ("sim", "iteration", "completed"))
        body = api.call_args_list[0].args[2]
        for key in ("assistantLlmOverride", "routingLlmOverride", "extractionLlmOverride"):
            self.assertEqual(body[key], freya.AGENT_LLM)

    def test_polling_timeout_is_not_success(self):
        replies = [{"id": "sim"}, {"status": "running"}, []]
        with patch.object(freya, "api", side_effect=replies), \
                patch.object(freya.time, "sleep"), \
                patch.object(freya.time, "monotonic", side_effect=[0, 901]):
            with self.assertRaisesRegex(TimeoutError, "polling deadline"):
                freya.run_simulation("agent", "test", {"persona": {}})

    def test_busy_workspace_wait_is_bounded(self):
        with patch.object(freya, "api", side_effect=RuntimeError("concurrent simulations")), \
                patch.object(freya.time, "sleep"), \
                patch.object(freya.time, "monotonic", side_effect=[0, 1, 901]):
            with self.assertRaisesRegex(TimeoutError, "workspace remained busy"):
                freya.run_simulation("agent", "test", {"persona": {}})

    def test_invalid_settings_do_not_start_a_simulation(self):
        with patch.object(freya, "api") as api:
            for kwargs in ({"concurrency": 0}, {"max_seconds": 0}):
                with self.assertRaises(ValueError):
                    freya.run_simulation("agent", "test", {"persona": {}}, **kwargs)
            with self.assertRaises(ValueError):
                freya.run_simulation("agent", "test", {})
        api.assert_not_called()
