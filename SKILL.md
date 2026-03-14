---
name: notebooklm
description: Automate Google NotebookLM via CLI for notebook/source management, chat, artifact generation, and downloads. Use when users ask to create podcast/video/report/quiz/flashcards, summarize sources, or manage NotebookLM content.
---

# NotebookLM Skill

Use this repository and CLI to automate Google NotebookLM.

## Purpose
- Manage notebooks, sources, notes, and artifacts.
- Ask questions and inspect conversation history.
- Generate artifacts (audio, video, report, quiz, flashcards, mind map, data table, slide deck, infographic).
- Download artifacts in local formats (`mp3`, `mp4`, `markdown`, `json`, `csv`, `pdf`, `pptx`, `html`).

## Environment Assumptions
- Python 3.10+ is available.
- Package is installed in the active environment.
- CLI command `notebooklm` is available.

## Authentication Rules
1. Before mutating workflows, run:
   - `notebooklm auth check`
2. If auth is invalid or missing, stop and tell the user:
   - "You are not logged in to NotebookLM. Please run `notebooklm login` and complete browser sign-in, then tell me to continue."
3. Do not claim login/auth succeeded without verification.
4. Do not continue with mutating commands (create/add/generate/download/delete/rename/save/share) until auth is confirmed.
5. In non-interactive environments, ask the user to provide `NOTEBOOKLM_AUTH_JSON`.

## Safe Execution Policy
- Read-only commands can run without confirmation:
  - `notebooklm auth check`
  - `notebooklm status`
  - `notebooklm list`
  - `notebooklm source list`
  - `notebooklm artifact list`
  - `notebooklm note list`
  - `notebooklm research status`
- Ask for confirmation before:
  - Destructive commands: `notebooklm delete ...`, `notebooklm source delete ...`, `notebooklm artifact delete ...`, `notebooklm note delete ...`
  - Long-running commands: `notebooklm generate ...`, `notebooklm research wait ...`, `notebooklm artifact wait ...`, `notebooklm source wait ...`
  - Filesystem writes: `notebooklm download ...`
  - Global settings: `notebooklm language set ...` (affects all notebooks)
  - Commands that write notebook content: `notebooklm note create/save/rename ...`, `notebooklm ask ... --save-as-note`, `notebooklm history --save`

## Minimal Workflow
1. Verify auth: `notebooklm auth check`
2. Select or create notebook:
   - `notebooklm use <id>`
   - or `notebooklm create "..." --json`
3. Add source:
   - `notebooklm source add "..." --json`
4. Wait for source readiness before ask/generate:
   - `notebooklm source wait <source_id>`
   - or poll `notebooklm source list --json` until status is `ready`
5. Ask or generate:
   - `notebooklm ask "..."`
   - `notebooklm generate ...`
6. Download output if needed:
   - `notebooklm download ...`

## Related Workflow Helper
- YouTube transcript extraction now lives in `/home/evan/my_skills/nanoclaw-workflows/workflows/notebooklm/youtube_transcript.py`.

## Parallel Agent Safety
- Do not rely on shared `notebooklm use` context in parallel workflows.
- Prefer explicit notebook IDs with `--notebook <id>` or `-n <id>` when supported.
- Prefer full UUIDs (not short prefixes) in automation.

## Output Style
- Keep responses short and actionable.
- Always include exact command(s) for the next user step.
- On auth failures, stop and ask the user to complete manual login first.
