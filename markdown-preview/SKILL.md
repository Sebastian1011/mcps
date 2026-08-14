---
name: markdown-preview
description: Open Markdown files in a live browser preview with automatic refresh, Mermaid diagrams, KaTeX math, syntax highlighting, task lists, tables, footnotes, and local images. Use when Codex or Claude needs to preview, visually inspect, or render a .md document while writing or reviewing it.
---

# Markdown Preview

Preview the user's Markdown in a local browser while preserving the editing loop.

## Start a preview

1. Resolve the requested Markdown file to an absolute path. If none is named, choose the only likely `.md` file in the working directory; ask only when multiple plausible files exist.
2. Run the bundled server from the skill directory:

   ```bash
   python3 scripts/preview.py /absolute/path/to/document.md
   ```

3. Keep the process running and report its printed URL. When the environment cannot open a browser, rerun with `--no-open` and give the URL to the user.
4. Leave the server running while the user edits or reviews the file. File changes appear automatically.
5. Stop the process with Ctrl-C when the user finishes or asks to close the preview.

Resolve `scripts/preview.py` relative to this `SKILL.md`, not relative to the user's project.

## Options

- Use `--no-open` in headless, remote, or sandboxed environments.
- Use `--port PORT` only when the user requests a stable port.
- Use `--theme light` or `--theme dark` when the user requests a theme. The default follows the operating system.
- Keep the default host `127.0.0.1`. Bind another host only when the user explicitly requests network access and understands that the document becomes reachable from that network.

Run `python3 scripts/preview.py --help` for the complete CLI.

## Verify rendering

- Confirm the server prints a URL and remains running.
- Fetch `/api/document` when browser access is unavailable; confirm it returns the expected path and content.
- Use an interactive browser tool for visual or frontend debugging when available.
- Treat browser console errors from CDN blocking as an environment limitation. The page still shows the Markdown source and explains that enhanced rendering could not load.

## Supported Markdown

Expect CommonMark-style Markdown plus tables, strikethrough, task lists, footnotes, syntax-highlighted fenced code, Mermaid fenced blocks, KaTeX inline/block math, and local relative images. Remote rendering libraries require access to `cdn.jsdelivr.net`.

Do not rewrite the user's Markdown merely to fit the previewer. Report unsupported syntax instead.
