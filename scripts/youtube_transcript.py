#!/usr/bin/env python3
"""Extract a YouTube transcript through NotebookLM.

Workflow:
1. Verify authentication with `notebooklm auth check`
2. Create a new notebook
3. Add the YouTube URL as a source
4. Wait for source processing
5. Fetch source fulltext and return transcript

Examples:
    uv run python scripts/youtube_transcript.py "https://www.youtube.com/watch?v=Mzkh_XVrs3A"
    uv run python scripts/youtube_transcript.py "https://youtu.be/Mzkh_XVrs3A" -o /tmp/transcript.txt
    uv run python scripts/youtube_transcript.py "<url>" --json --normalize-cjk-spacing
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_TIMEOUT_SECONDS = 300
CLI_CANDIDATES = (
    ['notebooklm'],
    ['uv', 'run', 'notebooklm'],
)


class NotebookLMCLIError(RuntimeError):
    """Raised when a notebooklm CLI command fails."""


def is_youtube_host(host: str) -> bool:
    """Return True if host belongs to YouTube."""
    return 'youtube.com' in host or 'youtu.be' in host


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Create a NotebookLM notebook from a YouTube URL and return transcript text.'
    )
    parser.add_argument('youtube_url', help='YouTube video URL (youtube.com or youtu.be)')
    parser.add_argument(
        '-t',
        '--title',
        help='Notebook title. Default: auto-generated from video ID',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f'Source processing timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})',
    )
    parser.add_argument(
        '-o',
        '--output',
        type=Path,
        help='Optional output file path for transcript text.',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Print JSON output (metadata + transcript) instead of plain transcript text.',
    )
    parser.add_argument(
        '--normalize-cjk-spacing',
        action='store_true',
        help='Remove spaces between adjacent CJK characters for better readability.',
    )
    parser.add_argument(
        '--cli',
        help="NotebookLM CLI command prefix. Example: 'notebooklm' or 'uv run notebooklm'.",
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress logs (errors are still shown).',
    )
    return parser.parse_args()


def is_youtube_url(url: str) -> bool:
    """Return True if URL looks like a YouTube link."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return is_youtube_host(parsed.netloc.lower())


def extract_video_id(url: str) -> str | None:
    """Extract a video id from common YouTube URL patterns."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split('/') if part]

    if 'youtu.be' in host:
        return path_parts[0] if path_parts else None

    if not is_youtube_host(host):
        return None

    query_video = parse_qs(parsed.query).get('v')
    if query_video:
        return query_video[0]

    if len(path_parts) >= 2 and path_parts[0] in {'shorts', 'live', 'embed'}:
        return path_parts[1]

    return None


def normalize_cjk_spacing(text: str) -> str:
    """Remove spaces between adjacent CJK characters."""
    return re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])', '', text)


def resolve_cli_prefix(cli_value: str | None) -> list[str]:
    """Resolve notebooklm CLI command prefix."""
    if cli_value:
        return shlex.split(cli_value)

    for candidate in CLI_CANDIDATES:
        try:
            result = subprocess.run(
                candidate + ['--version'],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return candidate

    raise NotebookLMCLIError(
        'Could not find `notebooklm` CLI. '
        'Install dependencies and run via `uv run`, or pass --cli explicitly.'
    )


def run_cli(cli_prefix: list[str], args: list[str]) -> str:
    """Run notebooklm CLI command and return stdout."""
    cmd = cli_prefix + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise NotebookLMCLIError(f"Command not found: {' '.join(cmd)}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or '(no output)'
        raise NotebookLMCLIError(f"Command failed: {' '.join(cmd)}\n{details}")

    return result.stdout


def load_json_output(raw_output: str, context: str) -> dict:
    """Parse command JSON output and raise helpful error if invalid."""
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise NotebookLMCLIError(f'Failed to parse JSON output from {context}.') from exc


def run_cli_json(cli_prefix: list[str], args: list[str], context: str) -> dict:
    """Run CLI command and parse JSON response."""
    return load_json_output(run_cli(cli_prefix, args), context)


def log(message: str, quiet: bool) -> None:
    """Print progress logs to stderr unless quiet mode is enabled."""
    if not quiet:
        print(message, file=sys.stderr)


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if not is_youtube_url(args.youtube_url):
        print('ERROR: `youtube_url` must be a valid youtube.com or youtu.be URL.', file=sys.stderr)
        return 2

    cli_prefix = resolve_cli_prefix(args.cli)
    video_id = extract_video_id(args.youtube_url) or 'unknown_video'
    notebook_title = args.title or f'YouTube Transcript - {video_id}'

    log(f"Using CLI: {' '.join(cli_prefix)}", args.quiet)
    log('Checking authentication...', args.quiet)
    run_cli(cli_prefix, ['auth', 'check'])

    log('Creating notebook...', args.quiet)
    create_output = run_cli_json(cli_prefix, ['create', notebook_title, '--json'], 'notebook create')
    notebook = create_output.get('notebook', {})
    notebook_id = notebook.get('id')
    if not notebook_id:
        raise NotebookLMCLIError('Notebook create output missing notebook id.')

    log('Adding YouTube source...', args.quiet)
    add_output = run_cli_json(
        cli_prefix,
        ['source', 'add', args.youtube_url, '-n', notebook_id, '--type', 'youtube', '--json'],
        'source add',
    )
    source = add_output.get('source', {})
    source_id = source.get('id')
    if not source_id:
        raise NotebookLMCLIError('Source add output missing source id.')

    log(f'Waiting for source ready (timeout={args.timeout}s)...', args.quiet)
    run_cli(
        cli_prefix,
        ['source', 'wait', source_id, '-n', notebook_id, '--timeout', str(args.timeout), '--json'],
    )

    log('Fetching transcript...', args.quiet)
    fulltext_output = run_cli_json(
        cli_prefix,
        ['source', 'fulltext', source_id, '-n', notebook_id, '--json'],
        'source fulltext',
    )
    transcript = fulltext_output.get('content', '')
    if not isinstance(transcript, str):
        raise NotebookLMCLIError('Unexpected fulltext content format.')

    if args.normalize_cjk_spacing:
        transcript = normalize_cjk_spacing(transcript)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(transcript, encoding='utf-8')
        log(f'Transcript saved: {args.output}', args.quiet)

    if args.json:
        payload = {
            'notebook_id': notebook_id,
            'notebook_title': notebook.get('title', notebook_title),
            'source_id': source_id,
            'source_title': source.get('title'),
            'char_count': len(transcript),
            'output_path': str(args.output) if args.output else None,
            'transcript': transcript,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(transcript)

    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        raise SystemExit(130)
    except NotebookLMCLIError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
