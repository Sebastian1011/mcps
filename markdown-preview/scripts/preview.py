#!/usr/bin/env python3
"""Serve a Markdown file with automatic browser refresh and rich rendering."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import posixpath
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse
import webbrowser


HTML = r"""<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net data:; img-src 'self' https: data:; connect-src 'self';">
  <title>Markdown Preview</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/markdown-it-texmath@1.0.0/css/texmath.min.css">
  <style>
    :root { color-scheme: light dark; --bg:#fff; --fg:#24292f; --muted:#59636e; --line:#d1d9e0; --code:#f6f8fa; --link:#0969da; }
    @media (prefers-color-scheme: dark) { :root { --bg:#0d1117; --fg:#f0f6fc; --muted:#9198a1; --line:#3d444d; --code:#151b23; --link:#4493f8; } }
    html[data-theme="light"] { color-scheme:light; --bg:#fff; --fg:#24292f; --muted:#59636e; --line:#d1d9e0; --code:#f6f8fa; --link:#0969da; }
    html[data-theme="dark"] { color-scheme:dark; --bg:#0d1117; --fg:#f0f6fc; --muted:#9198a1; --line:#3d444d; --code:#151b23; --link:#4493f8; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { position:sticky; top:0; z-index:2; display:flex; gap:1rem; align-items:center; padding:.55rem 1rem; border-bottom:1px solid var(--line); background:color-mix(in srgb,var(--bg) 92%,transparent); backdrop-filter:blur(8px); }
    header strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    #status { margin-left:auto; color:var(--muted); font-size:.85rem; white-space:nowrap; }
    main { max-width:980px; margin:0 auto; padding:2rem 2.5rem 5rem; overflow-wrap:anywhere; }
    h1,h2 { border-bottom:1px solid var(--line); padding-bottom:.3em; } h1,h2,h3,h4 { line-height:1.25; margin-top:1.5em; }
    a { color:var(--link); } img { max-width:100%; height:auto; }
    pre,code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; } code { background:var(--code); padding:.15em .35em; border-radius:5px; }
    pre { background:var(--code); padding:1rem; overflow:auto; border-radius:6px; } pre code { padding:0; background:transparent; }
    blockquote { margin-left:0; padding-left:1rem; color:var(--muted); border-left:.25rem solid var(--line); }
    table { border-spacing:0; border-collapse:collapse; display:block; overflow:auto; } th,td { padding:.4rem .8rem; border:1px solid var(--line); }
    tr:nth-child(2n) { background:var(--code); } hr { border:0; border-top:1px solid var(--line); }
    .task-list-item { list-style:none; } .task-list-item input { margin:0 .45rem 0 -1.3rem; }
    .mermaid { text-align:center; background:transparent; }
    #fallback { display:none; white-space:pre-wrap; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
    #notice { display:none; padding:.75rem 1rem; border:1px solid #bf8700; border-radius:6px; background:#fff8c5; color:#4d2d00; }
    @media (max-width:680px) { main { padding:1rem 1rem 4rem; } }
  </style>
</head>
<body>
  <header><strong id="filename">Markdown Preview</strong><span id="status">Loading…</span></header>
  <main><p id="notice"></p><article id="content"></article><pre id="fallback"></pre></main>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it-task-lists@2.1.1/dist/markdown-it-task-lists.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it-footnote@4.0.0/dist/markdown-it-footnote.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/markdown-it-texmath@1.0.0/texmath.min.js"></script>
  <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js"></script>
  <script>
    let revision = null;
    const content = document.getElementById('content');
    const fallback = document.getElementById('fallback');
    const notice = document.getElementById('notice');
    const status = document.getElementById('status');
    const filename = document.getElementById('filename');
    const escapeHtml = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    function renderer() {
      if (!window.markdownit) return null;
      const md = window.markdownit({ html:false, linkify:true, typographer:true,
        highlight: (str, lang) => {
          if (window.hljs && lang && hljs.getLanguage(lang)) return '<pre><code class="hljs">' + hljs.highlight(str, {language:lang, ignoreIllegals:true}).value + '</code></pre>';
          return '<pre><code>' + escapeHtml(str) + '</code></pre>';
        }
      });
      if (window.markdownitTaskLists) md.use(window.markdownitTaskLists, {enabled:false, label:true});
      if (window.markdownitFootnote) md.use(window.markdownitFootnote);
      if (window.texmath && window.katex) md.use(window.texmath, {engine:window.katex, delimiters:'dollars'});
      const fence = md.renderer.rules.fence.bind(md.renderer.rules);
      md.renderer.rules.fence = (tokens, idx, options, env, self) => {
        if (tokens[idx].info.trim() === 'mermaid') return '<div class="mermaid">' + escapeHtml(tokens[idx].content) + '</div>';
        return fence(tokens, idx, options, env, self);
      };
      const image = md.renderer.rules.image || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
      md.renderer.rules.image = (tokens, idx, options, env, self) => {
        const src = tokens[idx].attrGet('src') || '';
        if (src && !/^(?:[a-z]+:|\/|#)/i.test(src)) tokens[idx].attrSet('src', '/files/' + src.split('/').map(encodeURIComponent).join('/'));
        return image(tokens, idx, options, env, self);
      };
      return md;
    }

    const md = renderer();
    if (window.mermaid) mermaid.initialize({startOnLoad:false, securityLevel:'strict', theme:'default'});

    async function update() {
      try {
        const response = await fetch('/api/document', {cache:'no-store'});
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const doc = await response.json();
        status.textContent = 'Live'; filename.textContent = doc.name; document.title = doc.name + ' — Markdown Preview';
        document.documentElement.dataset.theme = doc.theme;
        if (doc.revision === revision) return;
        revision = doc.revision;
        if (!md) {
          notice.style.display = 'block'; notice.textContent = 'Enhanced renderer unavailable (the CDN may be blocked). Showing Markdown source.';
          fallback.style.display = 'block'; fallback.textContent = doc.content; return;
        }
        const source = doc.content.replace(/^---\s*\n[\s\S]*?\n---\s*(?:\n|$)/, '');
        fallback.style.display = 'none'; notice.style.display = 'none'; content.innerHTML = md.render(source);
        if (window.mermaid) {
          document.querySelectorAll('.mermaid').forEach(el => el.removeAttribute('data-processed'));
          try { await mermaid.run({nodes:document.querySelectorAll('.mermaid')}); }
          catch (error) { notice.style.display='block'; notice.textContent='Mermaid error: ' + error.message; }
        }
      } catch (error) { status.textContent = 'Disconnected'; }
    }
    update(); setInterval(update, 700);
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a live browser preview of a Markdown file.")
    parser.add_argument("file", type=Path, help="Markdown file to preview")
    parser.add_argument("--host", default="127.0.0.1", help="listen address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="listen port; 0 chooses a free port")
    parser.add_argument("--theme", choices=("system", "light", "dark"), default="system")
    parser.add_argument("--no-open", action="store_true", help="do not open the system browser")
    return parser.parse_args()


def is_loopback(host: str) -> bool:
    try:
        return all(addr[4][0].startswith("127.") or addr[4][0] == "::1" for addr in socket.getaddrinfo(host, None))
    except socket.gaierror:
        return False


def make_handler(document: Path, theme: str) -> type[BaseHTTPRequestHandler]:
    root = document.parent

    class PreviewHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/":
                self.send_bytes(HTML.encode(), "text/html; charset=utf-8")
            elif route == "/api/document":
                try:
                    stat = document.stat()
                    payload = {"name": document.name, "path": str(document), "content": document.read_text(encoding="utf-8"), "revision": stat.st_mtime_ns, "theme": theme}
                    self.send_bytes(json.dumps(payload).encode(), "application/json; charset=utf-8", cache=False)
                except (OSError, UnicodeError) as error:
                    self.send_error(500, str(error))
            elif route.startswith("/files/"):
                relative = posixpath.normpath(unquote(route.removeprefix("/files/"))).lstrip("/")
                target = (root / relative).resolve()
                if os.path.commonpath((root, target)) != str(root) or not target.is_file():
                    self.send_error(404)
                    return
                self.send_bytes(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            else:
                self.send_error(404)

        def send_bytes(self, body: bytes, content_type: str, cache: bool = True) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "private, max-age=3600" if cache else "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            if args and str(args[1])[:1] not in {"2", "3"}:
                super().log_message(fmt, *args)

    return PreviewHandler


def main() -> None:
    args = parse_args()
    document = args.file.expanduser().resolve()
    if not document.is_file():
        raise SystemExit(f"Markdown file not found: {document}")
    if document.suffix.lower() not in {".md", ".markdown", ".mdown", ".mkd"}:
        raise SystemExit(f"Not a recognized Markdown file: {document}")
    if not is_loopback(args.host):
        print(f"Warning: serving {document} on non-loopback host {args.host}; network peers may read it.", flush=True)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(document, args.theme))
    shown_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{shown_host}:{server.server_port}/"
    print(f"Previewing {document}", flush=True)
    print(f"URL: {url}", flush=True)
    print("Press Ctrl-C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
