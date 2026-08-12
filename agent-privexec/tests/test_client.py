#!/usr/bin/env python3
"""Unit tests for the unprivileged agent-privexec client."""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import stat
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = runpy.run_path(os.path.join(ROOT, "system/bin/agent-privexec"))


class PkexecPreflightTests(unittest.TestCase):
    def test_initial_user_namespace_does_not_remap_root(self) -> None:
        self.assertFalse(CLIENT["root_is_remapped"]("0 0 4294967295\n"))

    def test_sandbox_mapping_remaps_root(self) -> None:
        self.assertTrue(CLIENT["root_is_remapped"]("1000 0 1\n"))

    def test_valid_pkexec_passes(self) -> None:
        info = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | stat.S_ISUID | 0o755)
        with mock.patch.object(CLIENT["os"], "stat", return_value=info):
            CLIENT["require_working_pkexec"]()

    def test_sandboxed_pkexec_reports_sandbox_escape(self) -> None:
        info = SimpleNamespace(st_uid=65534, st_mode=stat.S_IFREG | stat.S_ISUID | 0o755)
        stderr = io.StringIO()
        with (
            mock.patch.object(CLIENT["os"], "stat", return_value=info),
            mock.patch("builtins.open", mock.mock_open(read_data="1000 0 1\n")),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            CLIENT["require_working_pkexec"]()

        self.assertEqual(raised.exception.code, CLIENT["EXIT_NO_AGENT"])
        self.assertIn("outside the agent sandbox", stderr.getvalue())

    def test_broken_host_pkexec_reports_unsafe_installation(self) -> None:
        info = SimpleNamespace(st_uid=1000, st_mode=stat.S_IFREG | 0o755)
        stderr = io.StringIO()
        with (
            mock.patch.object(CLIENT["os"], "stat", return_value=info),
            mock.patch("builtins.open", mock.mock_open(read_data="0 0 4294967295\n")),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            CLIENT["require_working_pkexec"]()

        self.assertEqual(raised.exception.code, CLIENT["EXIT_NO_AGENT"])
        self.assertIn("must be owned by root and have its setuid bit", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
