#!/usr/bin/env python3
"""Tests for audit-llm-calls.py"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importlib.util

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit_llm_calls = _load_module("audit_llm_calls", "audit-llm-calls.py")


class TestAuditLlmCalls(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, rel: str, content: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_detects_openai_call_without_output_limit(self) -> None:
        self.write(
            "app.py",
            '''
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "hello"}],
)
''',
        )
        reports, errors = audit_llm_calls.scan_project(self.root)
        self.assertEqual(errors, [])
        findings = [f for r in reports for f in r.findings]
        categories = {f.category for f in findings}
        self.assertIn("missing_output_limit", categories)
        self.assertIn("expensive_model", categories)

    def test_no_missing_limit_when_max_tokens_present(self) -> None:
        self.write(
            "good.py",
            '''
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    max_tokens=200,
)
''',
        )
        reports, _ = audit_llm_calls.scan_project(self.root)
        findings = [f for r in reports for f in r.findings]
        self.assertFalse(any(f.category == "missing_output_limit" for f in findings))

    def test_detects_typescript_ai_sdk(self) -> None:
        self.write(
            "agent.ts",
            '''
import { generateText } from "ai";
const result = await generateText({ model, prompt: "classify this" });
''',
        )
        reports, _ = audit_llm_calls.scan_project(self.root)
        llm_calls = [c for r in reports for c in r.llm_calls]
        self.assertTrue(any(label == "ai_sdk" for _, label in llm_calls))

    def test_detects_repeated_prompt_string(self) -> None:
        prompt = "You are a helpful assistant. " * 10
        self.write("prompts.py", f'SYSTEM_PROMPT = "{prompt}"\n')
        self.write("copy.py", f'SYSTEM_PROMPT = "{prompt}"\n')
        reports, _ = audit_llm_calls.scan_project(self.root)
        findings = [f for r in reports for f in r.findings]
        self.assertTrue(any(f.category == "repeated_prompt" for f in findings))

    def test_detects_unbounded_history(self) -> None:
        self.write("chat.py", "messages.push(new_message)\n")
        reports, _ = audit_llm_calls.scan_project(self.root)
        findings = [f for r in reports for f in r.findings]
        self.assertTrue(any(f.category == "unbounded_history" for f in findings))

    def test_skips_node_modules(self) -> None:
        self.write(
            "node_modules/pkg/index.js",
            'openai.chat.completions.create({ model: "gpt-4" })',
        )
        self.write("src/app.ts", "// no llm here\n")
        reports, _ = audit_llm_calls.scan_project(self.root)
        paths = [r.path for r in reports]
        self.assertFalse(any("node_modules" in p for p in paths))

    def test_nonexistent_path_returns_error(self) -> None:
        reports, errors = audit_llm_calls.scan_project(Path("/nonexistent/path/xyz"))
        self.assertEqual(reports, [])
        self.assertTrue(any("does not exist" in e for e in errors))

    def test_markdown_report_contains_summary(self) -> None:
        self.write(
            "bot.py",
            'client.chat.completions.create(model="gpt-4", messages=[])\n',
        )
        reports, errors = audit_llm_calls.scan_project(self.root)
        md = audit_llm_calls.render_markdown(self.root, reports, errors)
        self.assertIn("# LLM Call Audit Report", md)
        self.assertIn("Missing output limits", md)

    def test_main_writes_output_file(self) -> None:
        self.write("x.py", 'openai.chat.completions.create(model="gpt-4")\n')
        out = self.root / "report.md"
        rc = audit_llm_calls.main([str(self.root), "--output", str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        self.assertIn("LLM Call Audit Report", out.read_text(encoding="utf-8"))

    def test_main_missing_directory_exits_nonzero(self) -> None:
        rc = audit_llm_calls.main(["/path/does/not/exist/audit-test"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
