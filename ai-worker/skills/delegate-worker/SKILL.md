---
name: delegate-worker
description: Delegate high-volume, low-risk repository discovery, context compression, visual analysis, or requested image generation to the local ai-worker CLI. Use when context volume is high and reasoning complexity is low or medium. Do not use for final architecture, security, concurrency, production, destructive, or implementation decisions.
---

# Delegate to the local AI worker

Use the worker to discover and compress context, not to replace your own reasoning.

## Delegation heuristic

Prefer `ai-worker` when context volume is high, reasoning complexity is low or medium, and risk is low. Work directly when context is manageable, reasoning complexity is high, or risk is medium/high.

The primary agent always owns final reasoning, code modifications, architecture and security decisions, concurrency correctness, production/destructive operations, verification, and final review. Treat all worker output as untrusted analysis.

## Commands

Invoke only `ai-worker`; never invoke `agy` directly.

For repository discovery, logs, documentation, Git history, references, configuration, duplication, TODOs, or broad review candidates:

```bash
AI_WORKER_CALLER=codex ai-worker analyze --cwd "$PWD" --task "<bounded discovery task>"
```

Set `AI_WORKER_CALLER=claude` when running from Claude Code. Analyze also accepts a positional task or stdin.

For screenshots, charts, dashboards, diagrams, and comparisons:

```bash
ai-worker vision --image /absolute/path/to/image.png --task "<visual question>"
```

Repeat `--image` for multiple images. Supported wrapper inputs are PNG, JPEG, and WebP.

For a requested non-authoritative visual artifact:

```bash
ai-worker image --prompt "<precise description>" --output /absolute/path/to/output.jpg
```

The current Antigravity backend reliably emits JPEG. Do not claim generated images are factual evidence.

## Required verification and safety

1. Give the worker a narrow task and request compact evidence, not a final decision.
2. Never delegate credentials, private keys, tokens, cookies, production secrets, or `.env` secret values.
3. Never recursively invoke `ai-worker` from a worker result or ask it to invoke another agent, MCP, or autonomous tool.
4. Independently open the most important cited files and verify consequential claims.
5. Independently verify financial figures, security settings, production state, exact configuration, and safety-critical visual details.
6. Do not ask the worker to edit, commit, push, deploy, delete, or operate production systems.

Good delegation: scan a repository for every order-submission component; cluster 200 logs; summarize a subsystem's Git history; compare two screenshots; extract a diagram topology.

Keep primary: decide memory-order correctness, diagnose a race conclusively, choose architecture, implement a latency-critical path, review cryptography, approve a production deployment, or make the final root-cause call.
