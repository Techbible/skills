#!/usr/bin/env python3
"""
Scan Python and TypeScript projects for LLM call sites and common token-waste patterns.

Read-only: does not modify application code.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "vendor",
}

SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}

# Likely LLM / inference API call patterns
LLM_CALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_chat", re.compile(r"(?:\b(?:openai|OpenAI)\b.*\.(?:chat\.)?completions\.create\b|\.chat\.completions\.create\s*\()")),
    ("openai_responses", re.compile(r"\bclient\.responses\.create\b|\bopenai\.responses\.create\b")),
    ("anthropic_messages", re.compile(r"\banthropic\b.*\.messages\.create\b|\bAnthropic\b")),
    ("google_genai", re.compile(r"\b(?:google\.generativeai|genai)\b|\bgenerateContent\b")),
    ("litellm", re.compile(r"\blitellm\.(?:completion|acompletion)\b")),
    ("langchain_invoke", re.compile(r"\b(?:llm|model|chat_model)\.(?:invoke|ainvoke|predict|call)\b")),
    ("ai_sdk", re.compile(r"\b(?:generateText|streamText|generateObject)\s*\(")),
    ("huggingface", re.compile(r"\b(?:InferenceClient|pipeline)\s*\(")),
    ("ollama", re.compile(r"\bollama\b.*\.(?:chat|generate)\b")),
    ("generic_complete", re.compile(r"\b(?:complete|chat|generate|inference)\s*\(", re.I)),
]

OUTPUT_LIMIT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("max_tokens", re.compile(r"\bmax_tokens\s*[:=]")),
    ("max_output_tokens", re.compile(r"\bmax_output_tokens\s*[:=]")),
    ("max_completion_tokens", re.compile(r"\bmax_completion_tokens\s*[:=]")),
    ("maxTokens", re.compile(r"\bmaxTokens\s*[:=]")),
]

EXPENSIVE_MODEL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("gpt-4", re.compile(r"['\"]gpt-4[^'\"]*['\"]", re.I)),
    ("gpt-4o", re.compile(r"['\"]gpt-4o[^'\"]*['\"]", re.I)),
    ("o1", re.compile(r"['\"]o1[^'\"]*['\"]", re.I)),
    ("o3", re.compile(r"['\"]o3[^'\"]*['\"]", re.I)),
    ("claude-opus", re.compile(r"['\"]claude[^'\"] opus[^'\"]*['\"]|['\"]claude-3-opus[^'\"]*['\"]", re.I)),
    ("claude-sonnet-4", re.compile(r"['\"]claude[^'\"]*sonnet[^'\"]*['\"]", re.I)),
    ("gemini-pro", re.compile(r"['\"]gemini[^'\"]*pro[^'\"]*['\"]", re.I)),
]

HISTORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("messages_push", re.compile(r"\bmessages\.(?:push|append)\s*\(")),
    ("history_append", re.compile(r"\b(?:history|conversation|chat_history)\.(?:push|append|concat)\b")),
    ("spread_messages", re.compile(r"\[\s*\.\.\.(?:messages|history|conversation)")),
    ("unbounded_slice", re.compile(r"\bmessages\s*\[\s*:\s*\]|\bhistory\s*\[\s*:\s*\]")),
]

PROMPT_STRING_MIN_LEN = 80


@dataclass
class Finding:
    category: str
    severity: str
    path: str
    line: int
    message: str
    snippet: str = ""


@dataclass
class FileReport:
    path: str
    llm_calls: list[tuple[int, str]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def iter_source_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in SCAN_EXTENSIONS:
                yield path


def read_file(path: Path) -> tuple[list[str], str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except OSError as exc:
            return [], f"Could not read file: {exc}"
    except OSError as exc:
        return [], f"Could not read file: {exc}"
    return text.splitlines(), None


def nearby_has_output_limit(lines: list[str], line_idx: int, window: int = 12) -> bool:
    start = max(0, line_idx - window)
    end = min(len(lines), line_idx + window + 1)
    block = "\n".join(lines[start:end])
    return any(p.search(block) for _, p in OUTPUT_LIMIT_PATTERNS)


def extract_string_literals(line: str) -> list[str]:
    literals: list[str] = []
    for match in re.finditer(r"(['\"])(?:\\.|(?!\1).)*\1", line):
        raw = match.group(0)
        if len(raw) >= 2:
            literals.append(raw[1:-1])
    return literals


def analyze_file(path: Path, root: Path) -> FileReport:
    rel = str(path.relative_to(root))
    report = FileReport(path=rel)
    lines, err = read_file(path)
    if err:
        report.findings.append(
            Finding("error", "info", rel, 0, err)
        )
        return report

    prompt_strings: Counter[str] = Counter()
    llm_call_lines: list[int] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue

        for label, pattern in LLM_CALL_PATTERNS:
            if pattern.search(line):
                report.llm_calls.append((i, label))
                llm_call_lines.append(i)
                if not nearby_has_output_limit(lines, i - 1):
                    report.findings.append(
                        Finding(
                            "missing_output_limit",
                            "warning",
                            rel,
                            i,
                            f"LLM call ({label}) with no nearby output token limit",
                            snippet=stripped[:120],
                        )
                    )

        for label, pattern in EXPENSIVE_MODEL_PATTERNS:
            if pattern.search(line):
                report.findings.append(
                    Finding(
                        "expensive_model",
                        "info",
                        rel,
                        i,
                        f"Hard-coded expensive model reference ({label})",
                        snippet=stripped[:120],
                    )
                )

        for label, pattern in HISTORY_PATTERNS:
            if pattern.search(line):
                report.findings.append(
                    Finding(
                        "unbounded_history",
                        "warning",
                        rel,
                        i,
                        f"Possible unbounded chat history growth ({label})",
                        snippet=stripped[:120],
                    )
                )

        for lit in extract_string_literals(line):
            if len(lit) >= PROMPT_STRING_MIN_LEN and (
                "system" in line.lower()
                or "prompt" in line.lower()
                or "instruction" in line.lower()
                or lit.count("\n") >= 2
            ):
                normalized = " ".join(lit.split())
                prompt_strings[normalized] += 1

        if re.search(r"\b(?:SYSTEM_PROMPT|system_prompt|SYSTEM_INSTRUCTIONS)\s*=", line):
            for lit in extract_string_literals(line):
                if len(lit) >= PROMPT_STRING_MIN_LEN:
                    prompt_strings[" ".join(lit.split())] += 1

    for text, count in prompt_strings.items():
        if count >= 2:
            preview = text[:100] + ("…" if len(text) > 100 else "")
            report.findings.append(
                Finding(
                    "repeated_prompt",
                    "warning",
                    rel,
                    0,
                    f"Repeated prompt string ({count} occurrences): \"{preview}\"",
                )
            )

    return report


def scan_project(root: Path) -> tuple[list[FileReport], list[str]]:
    errors: list[str] = []
    if not root.exists():
        return [], [f"Path does not exist: {root}"]
    if not root.is_dir():
        return [], [f"Path is not a directory: {root}"]

    reports: list[FileReport] = []
    try:
        files = list(iter_source_files(root))
    except OSError as exc:
        return [], [f"Failed to walk directory: {exc}"]

    if not files:
        errors.append(f"No Python or TypeScript source files found under {root}")

    for path in files:
        reports.append(analyze_file(path, root))

    return reports, errors


def render_markdown(root: Path, reports: list[FileReport], errors: list[str]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# LLM Call Audit Report",
        "",
        f"**Project:** `{root}`  ",
        f"**Generated:** {now}  ",
        f"**Scanned files:** {len(reports)}",
        "",
    ]

    if errors:
        lines.extend(["## Errors", ""])
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    files_with_calls = [r for r in reports if r.llm_calls]
    all_findings = [f for r in reports for f in r.findings if f.category != "error"]

    lines.extend([
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Files with LLM calls | {len(files_with_calls)} |",
        f"| Total LLM call sites | {sum(len(r.llm_calls) for r in reports)} |",
        f"| Missing output limits | {sum(1 for f in all_findings if f.category == 'missing_output_limit')} |",
        f"| Repeated prompts | {sum(1 for f in all_findings if f.category == 'repeated_prompt')} |",
        f"| Unbounded history hints | {sum(1 for f in all_findings if f.category == 'unbounded_history')} |",
        f"| Expensive model references | {sum(1 for f in all_findings if f.category == 'expensive_model')} |",
        "",
    ])

    if files_with_calls:
        lines.extend(["## LLM call sites", ""])
        for report in sorted(files_with_calls, key=lambda r: r.path):
            lines.append(f"### `{report.path}`")
            lines.append("")
            for line_no, label in report.llm_calls:
                lines.append(f"- Line {line_no}: `{label}`")
            lines.append("")

    findings_by_category: dict[str, list[Finding]] = {}
    for f in all_findings:
        findings_by_category.setdefault(f.category, []).append(f)

    category_titles = {
        "missing_output_limit": "Missing output token limits",
        "repeated_prompt": "Repeated prompt strings",
        "unbounded_history": "Possible unbounded chat history",
        "expensive_model": "Hard-coded expensive models",
    }

    for category, title in category_titles.items():
        items = findings_by_category.get(category, [])
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for f in sorted(items, key=lambda x: (x.path, x.line)):
            loc = f"`{f.path}`" + (f" line {f.line}" if f.line else "")
            lines.append(f"- **{f.severity.upper()}** {loc}: {f.message}")
            if f.snippet:
                lines.append(f"  ```")
                lines.append(f"  {f.snippet}")
                lines.append(f"  ```")
        lines.append("")

    read_errors = [f for r in reports for f in r.findings if f.category == "error"]
    if read_errors:
        lines.extend(["## File read issues", ""])
        for f in read_errors:
            lines.append(f"- `{f.path}`: {f.message}")
        lines.append("")

    if not files_with_calls and not all_findings:
        lines.extend([
            "## Result",
            "",
            "No LLM call sites or token-waste patterns detected. "
            "The project may use indirect wrappers, config-driven models, or unsupported SDK patterns.",
            "",
        ])

    lines.extend([
        "---",
        "",
        "*Generated by Eli Token Optimizer `audit-llm-calls.py` (read-only scan).*",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan Python/TypeScript projects for LLM calls and token-waste patterns.",
    )
    parser.add_argument(
        "project_root",
        type=Path,
        help="Root directory of the project to scan",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Write Markdown report to this file (default: stdout)",
    )
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    reports, errors = scan_project(root)
    markdown = render_markdown(root, reports, errors)

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown, encoding="utf-8")
            print(f"Report written to {args.output}", file=sys.stderr)
        except OSError as exc:
            print(f"Error writing report: {exc}", file=sys.stderr)
            return 1
    else:
        print(markdown)

    return 0 if not any("does not exist" in e or "not a directory" in e for e in errors) else 1


if __name__ == "__main__":
    sys.exit(main())
