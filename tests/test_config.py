import json
import tempfile
import unittest
from pathlib import Path

from agent_router.config import load_config, resolve_config_path

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "subagent-driven-development-multi"
SHIPPED = SKILL_ROOT / "config" / "agents.json"
SONNET = "agent-platform/anthropic/claude-sonnet-5-5"
OPUS = "agent-platform/anthropic/claude-opus-5-5"


class ShippedConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(SHIPPED)

    def test_only_three_agents_are_enabled(self) -> None:
        enabled = {name for name, agent in self.config.agents.items() if agent.enabled}
        self.assertEqual(enabled, {"opencode", "codex", "claude"})

    def test_cursor_and_alter_are_listed_disabled(self) -> None:
        self.assertFalse(self.config.agents["cursor"].enabled)
        self.assertFalse(self.config.agents["alter"].enabled)

    def test_opencode_is_limited_to_sonnet_and_opus_with_all_efforts(self) -> None:
        agent = self.config.agents["opencode"]
        self.assertEqual(agent.allowed_models, (SONNET, OPUS))
        self.assertEqual(agent.efforts, ("low", "medium", "high", "xhigh", "max"))

    def test_codex_and_claude_have_no_model_restriction(self) -> None:
        self.assertIsNone(self.config.agents["codex"].allowed_models)
        self.assertIsNone(self.config.agents["claude"].allowed_models)


class ValidationTest(unittest.TestCase):
    def _write(self, data: dict[str, object]) -> Path:
        path = Path(tempfile.mkdtemp()) / "agents.json"
        path.write_text(json.dumps(data))
        return path

    def _base(self) -> dict[str, object]:
        return json.loads(SHIPPED.read_text())

    def test_tier_outside_allowed_models_is_rejected(self) -> None:
        data = self._base()
        data["agents"]["opencode"]["tiers"]["cheap"] = "other/model"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "opencode"):
            load_config(self._write(data))

    def test_unknown_agent_in_order_is_rejected(self) -> None:
        data = self._base()
        data["order"] = ["nope"]
        with self.assertRaisesRegex(ValueError, "nope"):
            load_config(self._write(data))

    def test_enabled_agent_without_command_is_rejected(self) -> None:
        data = self._base()
        data["agents"]["alter"]["enabled"] = True  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "alter"):
            load_config(self._write(data))

    def test_enabled_agent_missing_from_order_is_rejected(self) -> None:
        data = self._base()
        data["order"] = ["opencode", "codex", "cursor", "alter"]
        with self.assertRaisesRegex(ValueError, "claude"):
            load_config(self._write(data))

    def test_disabled_agent_may_be_missing_from_order(self) -> None:
        data = self._base()
        data["order"] = ["opencode", "codex", "claude"]
        self.assertEqual(load_config(self._write(data)).order, ("opencode", "codex", "claude"))

    def test_non_string_add_dir_flag_is_rejected(self) -> None:
        data = self._base()
        data["agents"]["codex"]["add_dir_flag"] = 5  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "add_dir_flag"):
            load_config(self._write(data))

    def test_invalid_token_pattern_is_rejected(self) -> None:
        data = self._base()
        data["agents"]["codex"]["token_error_patterns"] = ["("]  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "regex"):
            load_config(self._write(data))

    def test_errors_name_the_config_path(self) -> None:
        data = self._base()
        data["order"] = "x"
        path = self._write(data)
        with self.assertRaisesRegex(ValueError, str(path)):
            load_config(path)
        path.write_text("{broken")
        with self.assertRaisesRegex(ValueError, str(path)):
            load_config(path)

    def test_missing_file_raises_lookup_error(self) -> None:
        with self.assertRaises(LookupError):
            load_config(Path("/nonexistent/agents.json"))


class ResolvePathTest(unittest.TestCase):
    def test_user_override_wins(self) -> None:
        home = Path(tempfile.mkdtemp())
        override = home / ".config/superpowers-multi-subagents/agents.json"
        override.parent.mkdir(parents=True)
        override.write_text("{}")
        self.assertEqual(resolve_config_path(SKILL_ROOT, home), override)

    def test_shipped_config_is_the_default(self) -> None:
        self.assertEqual(resolve_config_path(SKILL_ROOT, Path(tempfile.mkdtemp())), SHIPPED)
