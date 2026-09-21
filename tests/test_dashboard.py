"""Tests for resolving VACA's startup dashboard path."""

import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "vaca" / "dashboard.py"
SPEC = spec_from_file_location("vaca_dashboard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
DASHBOARD = module_from_spec(SPEC)
SPEC.loader.exec_module(DASHBOARD)
resolve_dashboard_path = DASHBOARD.resolve_dashboard_path
merge_options = DASHBOARD.merge_options


class ResolveDashboardPathTests(unittest.TestCase):
    """Verify dashboard source precedence and path normalization."""

    def test_view_assist_path_takes_precedence(self) -> None:
        self.assertEqual(
            resolve_dashboard_path("/view-assist/home", "echo-show/home"),
            "view-assist/home",
        )

    def test_standalone_path_is_used_without_view_assist(self) -> None:
        self.assertEqual(
            resolve_dashboard_path("", "/echo-show/home"),
            "echo-show/home",
        )

    def test_empty_sources_keep_home_assistant_default(self) -> None:
        self.assertEqual(resolve_dashboard_path(None, None), "")

    def test_only_one_leading_slash_is_removed(self) -> None:
        self.assertEqual(
            resolve_dashboard_path("", "//echo-show/home"), "/echo-show/home"
        )

    def test_whitespace_view_assist_path_uses_standalone_path(self) -> None:
        self.assertEqual(
            resolve_dashboard_path("   ", " echo-show/home "),
            "echo-show/home",
        )


class MergeOptionsTests(unittest.TestCase):
    """Verify omitted options are preserved and explicit values replace them."""

    def test_omitted_option_is_preserved(self) -> None:
        self.assertEqual(
            merge_options(
                {"ha_url": "http://homeassistant.local:8123", "ha_dashboard": "home"},
                {"ha_dashboard": "wall-panel"},
            ),
            {
                "ha_url": "http://homeassistant.local:8123",
                "ha_dashboard": "wall-panel",
            },
        )

    def test_explicit_empty_value_clears_option(self) -> None:
        self.assertEqual(
            merge_options(
                {"ha_url": "http://homeassistant.local:8123", "ha_dashboard": "home"},
                {"ha_dashboard": ""},
            ),
            {
                "ha_url": "http://homeassistant.local:8123",
                "ha_dashboard": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
