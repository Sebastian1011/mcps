#!/usr/bin/env python3
"""Checks for the desktop authentication prompt."""

from __future__ import annotations

import os
import unittest
import xml.etree.ElementTree as ET


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(ROOT, "system/polkit/com.local.agent-privexec.policy")


class PolkitPromptTests(unittest.TestCase):
    def test_every_localized_message_shows_the_requested_command(self) -> None:
        action = ET.parse(POLICY).getroot().find("./action")
        self.assertIsNotNone(action)
        messages = action.findall("message")
        self.assertGreaterEqual(len(messages), 1)
        for message in messages:
            self.assertIn("$(command_line)", message.text or "")


if __name__ == "__main__":
    unittest.main()
