import unittest
from pathlib import Path

from agent_router.config import load_config
from agent_router.doctor import check_agents

SHIPPED = (
    Path(__file__).resolve().parents[1]
    / "skills/subagent-driven-development-multi/config/agents.json"
)


class DoctorTest(unittest.TestCase):
    def test_reports_missing_binary_and_skips_host_and_disabled(self) -> None:
        config = load_config(SHIPPED)
        results = check_agents(config, "claude", lambda name: None if name == "codex" else f"/bin/{name}")
        by_name = {result.name: result for result in results}
        self.assertEqual(set(by_name), {"opencode", "codex"})
        self.assertTrue(by_name["opencode"].ok)
        self.assertFalse(by_name["codex"].ok)
