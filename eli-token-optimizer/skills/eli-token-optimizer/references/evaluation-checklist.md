# Evaluation Checklist

Measure cost and quality **before and after** every optimization. Token reduction alone is not success — lower **cost per successful task** is.

---

## Core metrics

| Metric | Definition | How to collect |
|--------|------------|----------------|
| Input tokens per request | Total prompt tokens sent to the model | Provider usage API, logs, OpenTelemetry spans |
| Output tokens per request | Total completion tokens returned | Provider usage API, response metadata |
| Model calls per completed task | LLM invocations from user intent to successful outcome | Trace agent loops; count spans per task_id |
| Cache-hit rate | `cache_hits / (cache_hits + cache_misses)` | Cache middleware metrics |
| Cost per successful task | `total_cost / successful_tasks` | Billing + task outcome tracker |
| Valid response rate | Responses passing schema/quality gate without retry | Validator logs |
| Human correction rate | Tasks requiring human edit after model output | Support tooling, review queues |
| Retry rate | `retries / total_attempts` | Agent loop logs, error counters |
| Task success score | Grader score (0–1) or pass/fail on eval set | Eval harness |
| P50 latency | Median end-to-end time per request | APM, span timestamps |
| P95 latency | 95th percentile end-to-end time | APM, span timestamps |

---

## Baseline capture template

Record before any code change:

```json
{
  "period": "2026-03-01 to 2026-03-07",
  "workload": "support-chat",
  "input_tokens_per_request": 4200,
  "output_tokens_per_request": 380,
  "model_calls_per_task": 2.4,
  "cache_hit_rate": 0.12,
  "total_cost_usd": 842.50,
  "attempts": 12000,
  "successes": 10800,
  "retries": 1800,
  "valid_response_rate": 0.94,
  "human_correction_rate": 0.08,
  "task_success_score": 0.87,
  "latency_p50_ms": 2100,
  "latency_p95_ms": 6800
}
```

---

## Per-change evaluation protocol

1. **Isolate one change** — do not bundle unrelated optimizations in the same measurement window.
2. **Keep a control group** when traffic allows (A/B or shadow traffic).
3. **Use the same eval set** before and after (held-out from training if optimizing prompts).
4. **Run for sufficient volume** — at least one full business cycle or ≥1,000 tasks.
5. **Review failures**, not only averages — inspect truncated JSON, cache wrong-answers, routing fallbacks.

### Pass criteria (default thresholds — adjust per product)

| Metric | Acceptable change |
|--------|-------------------|
| Cost per successful task | Decrease ≥10% OR flat with quality gain |
| Valid response rate | Drop ≤1 absolute point |
| Retry rate | Increase ≤2 absolute points |
| Task success score | Drop ≤0.02 absolute |
| Human correction rate | Increase ≤2 absolute points |
| P95 latency | Increase ≤15% (caching/routing may improve this) |

If any threshold is exceeded, roll back or tune before proceeding.

---

## Security and data-isolation checks

Run these before enabling caching, routing, or compression in production:

### Tenant isolation
- [ ] Cache keys include `tenant_id` (or equivalent org scope)
- [ ] Semantic cache filtered by tenant at query time
- [ ] Batch job outputs scoped to submitting tenant
- [ ] Cross-tenant cache poisoning test passes

### Permission boundaries
- [ ] Cache key includes user role or permission hash when response varies by role
- [ ] RAG retrieval respects document-level ACLs before and after pruning
- [ ] Routed model tier does not bypass content filters on economy path

### Data freshness
- [ ] Cache TTL defined per workload type
- [ ] `prompt_version` in cache key; bumped on policy changes
- [ ] Semantic cache entries expire; stale answers invalidated on product update
- [ ] Live-data queries excluded from semantic cache

### Secrets and PII
- [ ] Prompts logged without API keys or raw credentials
- [ ] Compression and trimming do not strip redaction markers
- [ ] Batch export files encrypted at rest with scoped access

---

## Technique-specific checks

| Technique | Extra verification |
|-----------|-------------------|
| Output token budget | Truncation rate, structured output parse rate |
| History trim | Memory-heavy conversation eval set |
| Exact cache | Cross-tenant miss test, stale policy test |
| Semantic cache | Near-miss wrong-answer rate |
| Model routing | Per-route success score, fallback rate |
| RAG pruning | Answer recall, citation accuracy |
| Prompt compression | Number/date/negation retention eval |
| Compact reasoning | Accuracy on math/planning eval set |

---

## Reporting

Use `scripts/estimate-token-savings.py` to compute:

- Token reduction (%)
- Request-cost reduction (%)
- Retry-adjusted cost
- Cost per successful task (before vs after)

Include in every optimization report:

1. Baseline and optimized JSON snapshots
2. Pass/fail against thresholds above
3. Sample failures with root cause
4. Monitoring dashboards or alerts to watch post-deploy

---

## Rollback triggers

Define upfront and automate where possible:

- Valid response rate drops >2 points for 15 minutes
- Retry rate doubles vs baseline
- Cache wrong-answer reports exceed N per hour
- P95 latency exceeds SLA for 10 consecutive minutes
- Human correction rate increases >5 points week-over-week
