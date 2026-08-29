#!/usr/bin/env python3
"""Tests for estimate-token-savings.py"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import importlib.util

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


estimate_token_savings = _load_module("estimate_token_savings", "estimate-token-savings.py")


BASELINE = {
    "input_tokens_per_request": 4000,
    "output_tokens_per_request": 400,
    "requests": 1000,
    "cost_usd": 500.0,
    "successful_tasks": 900,
    "retries": 150,
    "attempts": 1000,
}

OPTIMIZED = {
    "input_tokens_per_request": 2500,
    "output_tokens_per_request": 300,
    "requests": 1000,
    "cost_usd": 320.0,
    "successful_tasks": 920,
    "retries": 120,
    "attempts": 1000,
}


class TestEstimateTokenSavings(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_json(self, name: str, data: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def write_csv(self, name: str, data: dict) -> Path:
        path = self.root / name
        headers = ",".join(data.keys())
        values = ",".join(str(v) for v in data.values())
        path.write_text(f"{headers}\n{values}\n", encoding="utf-8")
        return path

    def test_compute_savings_json(self) -> None:
        baseline = estimate_token_savings.parse_snapshot(BASELINE, "baseline")
        optimized = estimate_token_savings.parse_snapshot(OPTIMIZED, "optimized")
        result = estimate_token_savings.compute_savings(baseline, optimized)

        self.assertGreater(result["savings"]["token_reduction_pct"], 0)
        self.assertGreater(result["savings"]["cost_reduction_usd"], 0)
        self.assertGreater(result["savings"]["cost_per_successful_task_reduction_pct"], 0)
        self.assertIn(result["savings"]["verdict"], {"success", "marginal"})

    def test_load_json_snapshot(self) -> None:
        path = self.write_json("baseline.json", BASELINE)
        snap = estimate_token_savings.load_snapshot(path, "baseline")
        self.assertEqual(snap.requests, 1000)
        self.assertAlmostEqual(snap.cost_per_successful_task, 500.0 / 900)

    def test_load_csv_snapshot(self) -> None:
        path = self.write_csv("baseline.csv", BASELINE)
        snap = estimate_token_savings.load_snapshot(path, "baseline")
        self.assertEqual(snap.input_tokens_per_request, 4000)

    def test_missing_required_field_raises(self) -> None:
        bad = {k: v for k, v in BASELINE.items() if k != "cost_usd"}
        with self.assertRaises(ValueError) as ctx:
            estimate_token_savings.parse_snapshot(bad, "baseline")
        self.assertIn("cost_usd", str(ctx.exception))

    def test_retry_regression_verdict(self) -> None:
        baseline = estimate_token_savings.parse_snapshot(BASELINE, "baseline")
        worse = dict(OPTIMIZED)
        worse["retries"] = 500
        optimized = estimate_token_savings.parse_snapshot(worse, "optimized")
        result = estimate_token_savings.compute_savings(baseline, optimized)
        self.assertEqual(result["savings"]["verdict"], "retry_regression")

    def test_markdown_report_render(self) -> None:
        baseline = estimate_token_savings.parse_snapshot(BASELINE, "baseline")
        optimized = estimate_token_savings.parse_snapshot(OPTIMIZED, "optimized")
        result = estimate_token_savings.compute_savings(baseline, optimized)
        md = estimate_token_savings.render_markdown(result)
        self.assertIn("# Token Savings Report", md)
        self.assertIn("Cost / successful task", md)

    def test_main_writes_outputs(self) -> None:
        b = self.write_json("b.json", BASELINE)
        o = self.write_json("o.json", OPTIMIZED)
        json_out = self.root / "out.json"
        md_out = self.root / "out.md"
        rc = estimate_token_savings.main([
            "--baseline", str(b),
            "--optimized", str(o),
            "--output-json", str(json_out),
            "--output-md", str(md_out),
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(json_out.exists())
        self.assertTrue(md_out.exists())
        data = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertIn("savings", data)

    def test_unsupported_format_raises(self) -> None:
        path = self.root / "data.txt"
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            estimate_token_savings.load_snapshot(path, "baseline")
        self.assertIn("Unsupported file format", str(ctx.exception))

    def test_csv_multiple_rows_raises(self) -> None:
        path = self.root / "multi.csv"
        path.write_text(
            "input_tokens_per_request,output_tokens_per_request,requests,cost_usd,successful_tasks\n"
            "1,2,3,4,5\n"
            "6,7,8,9,10\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as ctx:
            estimate_token_savings.load_snapshot(path, "baseline")
        self.assertIn("exactly one data row", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
