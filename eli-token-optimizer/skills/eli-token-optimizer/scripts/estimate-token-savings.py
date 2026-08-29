#!/usr/bin/env python3
"""
Compare baseline vs optimized LLM usage and estimate token/cost savings.

Accepts JSON or CSV input. Produces JSON and Markdown output.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "input_tokens_per_request",
    "output_tokens_per_request",
    "requests",
    "cost_usd",
    "successful_tasks",
}

OPTIONAL_FIELDS = {
    "retries": 0,
    "attempts": None,  # defaults to requests if omitted
    "model_calls_per_task": None,
    "cache_hit_rate": None,
    "valid_response_rate": None,
    "human_correction_rate": None,
    "task_success_score": None,
    "latency_p50_ms": None,
    "latency_p95_ms": None,
}


@dataclass
class UsageSnapshot:
    input_tokens_per_request: float
    output_tokens_per_request: float
    requests: int
    cost_usd: float
    successful_tasks: int
    retries: int = 0
    attempts: int | None = None
    model_calls_per_task: float | None = None
    cache_hit_rate: float | None = None
    valid_response_rate: float | None = None
    human_correction_rate: float | None = None
    task_success_score: float | None = None
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None

    @property
    def attempts_resolved(self) -> int:
        return self.attempts if self.attempts is not None else self.requests

    @property
    def total_input_tokens(self) -> float:
        return self.input_tokens_per_request * self.requests

    @property
    def total_output_tokens(self) -> float:
        return self.output_tokens_per_request * self.requests

    @property
    def total_tokens(self) -> float:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def cost_per_request(self) -> float:
        return self.cost_usd / self.requests if self.requests else 0.0

    @property
    def cost_per_successful_task(self) -> float:
        return self.cost_usd / self.successful_tasks if self.successful_tasks else 0.0

    @property
    def retry_adjusted_cost_per_success(self) -> float:
        if not self.successful_tasks:
            return 0.0
        multiplier = self.attempts_resolved / self.successful_tasks
        return (self.cost_usd * multiplier) / self.successful_tasks


def _coerce_number(value: Any, field: str) -> float:
    if value is None or value == "":
        raise ValueError(f"Missing required numeric field: {field}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field}: {value!r}") from exc


def _coerce_int(value: Any, field: str) -> int:
    num = _coerce_number(value, field)
    if num != int(num):
        raise ValueError(f"{field} must be an integer, got {value!r}")
    return int(num)


def parse_snapshot(data: dict[str, Any], label: str) -> UsageSnapshot:
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"{label} data missing required fields: {', '.join(sorted(missing))}. "
            f"Required: {', '.join(sorted(REQUIRED_FIELDS))}"
        )

    snapshot = UsageSnapshot(
        input_tokens_per_request=_coerce_number(data["input_tokens_per_request"], "input_tokens_per_request"),
        output_tokens_per_request=_coerce_number(data["output_tokens_per_request"], "output_tokens_per_request"),
        requests=_coerce_int(data["requests"], "requests"),
        cost_usd=_coerce_number(data["cost_usd"], "cost_usd"),
        successful_tasks=_coerce_int(data["successful_tasks"], "successful_tasks"),
    )

    if "retries" in data and data["retries"] not in (None, ""):
        snapshot.retries = _coerce_int(data["retries"], "retries")
    if "attempts" in data and data["attempts"] not in (None, ""):
        snapshot.attempts = _coerce_int(data["attempts"], "attempts")

    for optional in (
        "model_calls_per_task",
        "cache_hit_rate",
        "valid_response_rate",
        "human_correction_rate",
        "task_success_score",
        "latency_p50_ms",
        "latency_p95_ms",
    ):
        if optional in data and data[optional] not in (None, ""):
            setattr(snapshot, optional, _coerce_number(data[optional], optional))

    if snapshot.requests <= 0:
        raise ValueError(f"{label}: requests must be > 0")
    if snapshot.successful_tasks <= 0:
        raise ValueError(f"{label}: successful_tasks must be > 0")

    return snapshot


def load_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object in {path}")
    return data


def load_csv(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc

    if not rows:
        raise ValueError(f"CSV file is empty: {path}")
    if len(rows) > 1:
        raise ValueError(
            f"CSV must contain exactly one data row (got {len(rows)}). "
            "Use JSON for multi-period data."
        )
    return {k: v for k, v in rows[0].items() if k}


def load_snapshot(path: Path, label: str) -> UsageSnapshot:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = load_json(path)
    elif suffix == ".csv":
        data = load_csv(path)
    else:
        raise ValueError(
            f"Unsupported file format for {path}: use .json or .csv"
        )
    return parse_snapshot(data, label)


def pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return ((after - before) / before) * 100.0


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def compute_savings(baseline: UsageSnapshot, optimized: UsageSnapshot) -> dict[str, Any]:
    baseline_tokens = baseline.total_tokens
    optimized_tokens = optimized.total_tokens
    token_reduction_pct = pct_change(baseline_tokens, optimized_tokens)
    if token_reduction_pct is not None:
        token_reduction_pct = -token_reduction_pct  # positive = savings

    cost_reduction_pct = pct_change(baseline.cost_usd, optimized.cost_usd)
    if cost_reduction_pct is not None:
        cost_reduction_pct = -cost_reduction_pct

    request_cost_reduction_pct = pct_change(baseline.cost_per_request, optimized.cost_per_request)
    if request_cost_reduction_pct is not None:
        request_cost_reduction_pct = -request_cost_reduction_pct

    cps_baseline = baseline.cost_per_successful_task
    cps_optimized = optimized.cost_per_successful_task
    cps_reduction_pct = pct_change(cps_baseline, cps_optimized)
    if cps_reduction_pct is not None:
        cps_reduction_pct = -cps_reduction_pct

    retry_adj_baseline = baseline.retry_adjusted_cost_per_success
    retry_adj_optimized = optimized.retry_adjusted_cost_per_success
    retry_adj_reduction_pct = pct_change(retry_adj_baseline, retry_adj_optimized)
    if retry_adj_reduction_pct is not None:
        retry_adj_reduction_pct = -retry_adj_reduction_pct

    return {
        "baseline": {
            "total_input_tokens": baseline.total_input_tokens,
            "total_output_tokens": baseline.total_output_tokens,
            "total_tokens": baseline_tokens,
            "cost_usd": baseline.cost_usd,
            "cost_per_request": baseline.cost_per_request,
            "cost_per_successful_task": cps_baseline,
            "retry_adjusted_cost_per_success": retry_adj_baseline,
            "retry_rate": baseline.retries / baseline.attempts_resolved if baseline.attempts_resolved else 0,
        },
        "optimized": {
            "total_input_tokens": optimized.total_input_tokens,
            "total_output_tokens": optimized.total_output_tokens,
            "total_tokens": optimized_tokens,
            "cost_usd": optimized.cost_usd,
            "cost_per_request": optimized.cost_per_request,
            "cost_per_successful_task": cps_optimized,
            "retry_adjusted_cost_per_success": retry_adj_optimized,
            "retry_rate": optimized.retries / optimized.attempts_resolved if optimized.attempts_resolved else 0,
        },
        "savings": {
            "token_reduction_absolute": baseline_tokens - optimized_tokens,
            "token_reduction_pct": token_reduction_pct,
            "cost_reduction_usd": baseline.cost_usd - optimized.cost_usd,
            "cost_reduction_pct": cost_reduction_pct,
            "request_cost_reduction_pct": request_cost_reduction_pct,
            "cost_per_successful_task_reduction_pct": cps_reduction_pct,
            "retry_adjusted_cost_reduction_pct": retry_adj_reduction_pct,
            "verdict": _verdict(cps_reduction_pct, baseline, optimized),
        },
    }


def _verdict(
    cps_reduction_pct: float | None,
    baseline: UsageSnapshot,
    optimized: UsageSnapshot,
) -> str:
    if cps_reduction_pct is None:
        return "insufficient_data"
    retry_worse = optimized.retries / max(optimized.attempts_resolved, 1) > (
        baseline.retries / max(baseline.attempts_resolved, 1) * 1.5
    )
    if retry_worse:
        return "retry_regression"
    if cps_reduction_pct >= 10:
        return "success"
    if cps_reduction_pct >= 0:
        return "marginal"
    return "cost_increase"


def render_markdown(result: dict[str, Any]) -> str:
    b = result["baseline"]
    o = result["optimized"]
    s = result["savings"]

    lines = [
        "# Token Savings Report",
        "",
        "## Summary",
        "",
        f"**Verdict:** `{s['verdict']}`",
        "",
        f"| Metric | Baseline | Optimized | Change |",
        f"|--------|----------|-----------|--------|",
        f"| Total tokens | {b['total_tokens']:,.0f} | {o['total_tokens']:,.0f} | {fmt_pct(-(s['token_reduction_pct'] or 0) if s['token_reduction_pct'] is not None else None)} saved |",
        f"| Total cost (USD) | ${b['cost_usd']:,.2f} | ${o['cost_usd']:,.2f} | {fmt_pct(-(s['cost_reduction_pct'] or 0) if s['cost_reduction_pct'] is not None else None)} saved |",
        f"| Cost / request | ${b['cost_per_request']:.4f} | ${o['cost_per_request']:.4f} | {fmt_pct(s['request_cost_reduction_pct'])} saved |",
        f"| Cost / successful task | ${b['cost_per_successful_task']:.4f} | ${o['cost_per_successful_task']:.4f} | {fmt_pct(s['cost_per_successful_task_reduction_pct'])} saved |",
        f"| Retry-adjusted cost / success | ${b['retry_adjusted_cost_per_success']:.4f} | ${o['retry_adjusted_cost_per_success']:.4f} | {fmt_pct(s['retry_adjusted_cost_reduction_pct'])} saved |",
        f"| Retry rate | {b['retry_rate']:.1%} | {o['retry_rate']:.1%} | |",
        "",
        "## Interpretation",
        "",
    ]

    verdict_notes = {
        "success": "Cost per successful task decreased by ≥10% without major retry regression.",
        "marginal": "Costs flat or slightly improved. Review quality metrics before scaling.",
        "cost_increase": "Optimized configuration costs more per successful task — investigate retries and quality.",
        "retry_regression": "Retry rate increased significantly. Token savings may be illusory.",
        "insufficient_data": "Could not compute percentage change (zero baseline).",
    }
    lines.append(verdict_notes.get(s["verdict"], ""))
    lines.extend([
        "",
        "---",
        "",
        "*Generated by Eli Token Optimizer `estimate-token-savings.py`.*",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate token and cost savings from baseline vs optimized usage.",
    )
    parser.add_argument("--baseline", "-b", type=Path, required=True, help="Baseline JSON or CSV")
    parser.add_argument("--optimized", "-O", type=Path, required=True, help="Optimized JSON or CSV")
    parser.add_argument("--output-json", type=Path, help="Write JSON results to file")
    parser.add_argument("--output-md", type=Path, help="Write Markdown report to file")
    args = parser.parse_args(argv)

    try:
        baseline = load_snapshot(args.baseline, "baseline")
        optimized = load_snapshot(args.optimized, "optimized")
        result = compute_savings(baseline, optimized)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    json_text = json.dumps(result, indent=2)
    md_text = render_markdown(result)

    if args.output_json:
        try:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json_text, encoding="utf-8")
            print(f"JSON written to {args.output_json}", file=sys.stderr)
        except OSError as exc:
            print(f"Error writing JSON: {exc}", file=sys.stderr)
            return 1
    else:
        print(json_text)

    if args.output_md:
        try:
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(md_text, encoding="utf-8")
            print(f"Markdown written to {args.output_md}", file=sys.stderr)
        except OSError as exc:
            print(f"Error writing Markdown: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
