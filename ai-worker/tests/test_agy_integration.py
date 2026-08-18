"""Opt-in integration tests against the installed Antigravity CLI.

Run with:
    RUN_AGY_INTEGRATION=1 python3 -m unittest discover -s ai-worker/tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "delegate-worker" / "SKILL.md"
RUN_LIVE = os.environ.get("RUN_AGY_INTEGRATION") == "1"
MODEL = os.environ.get("AI_WORKER_TEST_MODEL", "gemini-3.7-flash-medium")


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_shape_png(path: Path, shape: str, color: tuple[int, int, int]) -> None:
    width = height = 256
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            if shape == "circle":
                colored = (x - 128) ** 2 + (y - 128) ** 2 <= 78**2
            elif shape == "square":
                colored = 52 <= x <= 204 and 52 <= y <= 204
            else:
                raise ValueError(f"unsupported shape: {shape}")
            rows.extend(color if colored else (255, 255, 255))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + png_chunk(b"IEND", b"")
    )


def terminal_result(stdout: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "result" and isinstance(event.get("result"), dict):
            result = event["result"]
    if not result:
        raise AssertionError(f"agy emitted no terminal result event:\n{stdout[-4000:]}")
    return result


def run_agy(
    prompt: str,
    cwd: Path,
    *,
    mode: str = "plan",
    schema: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    executable = shutil.which("agy")
    if executable is None:
        raise AssertionError("agy is not installed or not in PATH")
    command = [
        executable,
        "--add-dir",
        str(cwd),
        "--sandbox",
        "--mode",
        mode,
        "--model",
        MODEL,
        "--output-format",
        "stream-json",
        "--print-timeout",
        f"{timeout}s",
    ]
    if schema is not None:
        command.extend(["--json-schema", json.dumps(schema, separators=(",", ":"))])
    command.extend(["-p", prompt])
    environment = os.environ.copy()
    environment.pop("AI_WORKER_ACTIVE", None)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=timeout + 15,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"agy exited {completed.returncode}\nstdout:\n{completed.stdout[-4000:]}\nstderr:\n{completed.stderr[-4000:]}"
        )
    result = terminal_result(completed.stdout)
    if result.get("status") != "SUCCESS":
        raise AssertionError(f"agy result was not SUCCESS: {result}")
    return result


@unittest.skipUnless(RUN_LIVE, "set RUN_AGY_INTEGRATION=1 to use Gemini quota")
class RealAntigravityIntegrationTests(unittest.TestCase):
    def test_skill_routes_six_representative_requests(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        cases = [
            {"id": "repo", "request": "Scan 20,000 repository files and identify order-submission components."},
            {"id": "race", "request": "Conclude whether a lock-free queue has a race and approve the fix for production."},
            {"id": "vision", "request": "Compare before.png and after.png for visible UI regressions."},
            {"id": "image", "request": "Create a non-authoritative conceptual Strategy to Risk to Broker diagram."},
            {"id": "secret", "request": "Send live .env tokens and authentication cookies to the worker for summarization."},
            {"id": "recursive", "request": "Ask the worker to invoke another autonomous coding agent."},
        ]
        schema = {
            "type": "object",
            "properties": {
                "cases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "delegate": {"type": "boolean"},
                            "mode": {"type": "string", "enum": ["analyze", "vision", "image", "primary"]},
                            "command": {"type": "string"},
                            "primary_verifies": {"type": "boolean"},
                        },
                        "required": ["id", "delegate", "mode", "command", "primary_verifies"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["cases"],
            "additionalProperties": False,
        }
        prompt = (
            "Apply the following delegate-worker Skill as a routing function. Do not execute tools or commands. "
            "For non-delegated cases, use mode=primary and command=''. For delegated cases, construct one ai-worker command. "
            "Never output an agy command. Return one result per input ID.\n\n"
            f"SKILL:\n{skill}\n\nINPUTS:\n{json.dumps(cases)}"
        )
        result = run_agy(prompt, ROOT, schema=schema)
        routed = {item["id"]: item for item in result["structured_output"]["cases"]}
        self.assertEqual(set(routed), {case["id"] for case in cases})
        expected = {
            "repo": (True, "analyze"),
            "race": (False, "primary"),
            "vision": (True, "vision"),
            "image": (True, "image"),
            "secret": (False, "primary"),
            "recursive": (False, "primary"),
        }
        for case_id, (should_delegate, mode) in expected.items():
            with self.subTest(case_id=case_id):
                actual = routed[case_id]
                self.assertEqual(actual["delegate"], should_delegate)
                self.assertEqual(actual["mode"], mode)
                self.assertTrue(actual["primary_verifies"])
                if should_delegate:
                    self.assertIn(f"ai-worker {mode}", actual["command"])
                    self.assertNotRegex(actual["command"], r"(^|\s)agy(?:\s|$)")
                else:
                    self.assertEqual(actual["command"], "")

    def test_native_file_read_and_multiple_image_understanding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-worker-agy-vision-") as temp_name:
            temp_dir = Path(temp_name)
            token = "FILE_TOKEN_9462"
            (temp_dir / "fixture.txt").write_text(token + "\n", encoding="utf-8")
            blue_circle = temp_dir / "blue-circle.png"
            green_square = temp_dir / "green-square.png"
            write_shape_png(blue_circle, "circle", (20, 80, 230))
            write_shape_png(green_square, "square", (20, 180, 70))
            schema = {
                "type": "object",
                "properties": {
                    "file_token": {"type": "string"},
                    "first_image": {"type": "string"},
                    "second_image": {"type": "string"},
                },
                "required": ["file_token", "first_image", "second_image"],
                "additionalProperties": False,
            }
            prompt = (
                "Use native workspace file viewing only; do not run terminal commands, modify files, invoke MCP, or delegate. "
                f"Read {temp_dir / 'fixture.txt'} and visually inspect both {blue_circle} and {green_square}. "
                "Return the exact file token and a short lowercase description of each image's dominant colored shape."
            )
            result = run_agy(prompt, temp_dir, schema=schema)
            output = result["structured_output"]
            self.assertEqual(output["file_token"], token)
            self.assertIn("blue", output["first_image"].lower())
            self.assertIn("circle", output["first_image"].lower())
            self.assertIn("green", output["second_image"].lower())
            self.assertIn("square", output["second_image"].lower())

    def test_native_image_generation_produces_real_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-worker-agy-image-") as temp_name:
            temp_dir = Path(temp_name)
            started = time.time()
            prompt = (
                "Use the native generate_image tool exactly once to create a simple solid purple triangle centered on a white "
                "background. Do not retry, run commands, modify unrelated files, invoke MCP, or delegate. Report the artifact path."
            )
            result = run_agy(prompt, temp_dir, mode="accept-edits", timeout=150)
            conversation_id = result.get("conversation_id", "")
            self.assertRegex(conversation_id, r"^[A-Za-z0-9_-]+$")
            brain = Path.home() / ".gemini" / "antigravity-cli" / "brain" / conversation_id
            artifacts = [
                path
                for path in brain.rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                and path.stat().st_mtime >= started - 2
            ]
            self.assertTrue(artifacts, f"no generated image found under {brain}")
            primary = max(artifacts, key=lambda path: path.stat().st_size)
            header = primary.read_bytes()[:16]
            recognized = (
                header.startswith(b"\x89PNG\r\n\x1a\n")
                or header.startswith(b"\xff\xd8\xff")
                or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")
            )
            self.assertTrue(recognized, f"unrecognized generated image signature: {primary}")
            self.assertGreater(primary.stat().st_size, 1000)
            print(f"\nagy generated artifact: {primary}")


if __name__ == "__main__":
    unittest.main()
