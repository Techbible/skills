---
name: eli-token-optimizer
description: >-
  Inspects AI applications for token waste and inference cost. Audits LLM call
  sites, prompt builders, agent loops, RAG pipelines, and evaluation code.
  Ranks optimization techniques by savings, effort, and quality risk. Use when
  the user mentions LLM costs, AI inference costs, token usage, prompt
  optimization, model routing, caching, RAG context, agent loops, batch
  processing, output token limits, repeated model calls, or expensive AI
  workloads.
---

# Eli Token Optimizer

Reduce inference cost without blindly downgrading models. Optimize the work around the model: fewer input tokens, fewer output tokens, fewer repeated calls, smarter routing.

**Cost equation:** `AI cost = input tokens + output tokens + model calls × price per token`

## When to use

- User asks to cut LLM, AI, or inference costs
- Token usage, prompt size, or model call volume is a concern
- Agent loops, RAG pipelines, or chat history may be unbounded
- Repeated model calls or missing output limits are suspected
- Before routing traffic to cheaper models or adding caching

## When not to use

- Pure model-selection questions with no code to inspect
- Non-AI performance tuning (database, frontend bundle size)
- Security audits unrelated to LLM cost
- Tasks that require changing product behavior without cost/quality tradeoff discussion

## Workflow

Copy this checklist and track progress:

```
Token optimization progress:
- [ ] Phase 1: Discover and baseline
- [ ] Phase 2: Audit and rank techniques
- [ ] Phase 3: Apply low-risk changes
- [ ] Phase 4: Evaluate and report
```

### Phase 1: Discover and baseline

1. **Run the audit script** on the target project root:

   ```bash
   python skills/eli-token-optimizer/scripts/audit-llm-calls.py /path/to/project --output audit-report.md
   ```

   If the plugin is installed under `.cursor/skills/` or `.agents/skills/`, adjust the path accordingly.

2. **Find manually** what the script may miss:
   - Model API wrappers and SDK clients
   - Prompt builders, system prompt templates, tool schemas
   - Agent loops (ReAct, tool-calling chains, multi-step planners)
   - RAG retrieval, reranking, and context assembly
   - Evaluation and grading pipelines

3. **Establish a baseline** before changing code. Capture from logs, billing, or eval runs:
   - Input tokens per request
   - Output tokens per request
   - Model calls per completed task
   - Cost per successful task
   - Valid response rate, retry rate, P50/P95 latency

   See [references/evaluation-checklist.md](references/evaluation-checklist.md) for the full metric set.

### Phase 2: Audit and rank techniques

1. Read [references/techniques.md](references/techniques.md) for all 16 techniques.
2. Map each technique to concrete findings in the codebase.
3. **Do not apply every technique.** Select only what fits current traffic and architecture.
4. Rank candidates using this matrix:

   | Technique | Expected savings | Engineering effort | Quality risk | Priority |
   |-----------|------------------|--------------------|--------------|----------|
   | …         | high/med/low     | low/med/high       | low/med/high | 1–N      |

5. Apply in phases (from techniques reference):
   - **Phase 1 quick wins:** concise output, output limits, whitespace normalization, JSON minify, duplicate collapse
   - **Phase 2 context/calls:** history trim, exact cache, stable prompt prefixes
   - **Phase 3 traffic:** model routing, batch APIs, lower-priority tiers, semantic cache
   - **Phase 4 advanced:** RAG pruning, prompt compression, eval-driven prompt optimization, compact reasoning

### Phase 3: Apply low-risk changes first

For each change:

1. Read the matching section in [references/implementation-patterns.md](references/implementation-patterns.md).
2. Implement the smallest diff that addresses the finding.
3. **Preserve:**
   - Output quality for the task's quality bar
   - Security boundaries (auth, PII, secrets)
   - Tenant isolation and user permissions in cache keys
   - Tool access scoping per user/tenant
4. Run existing tests after every material change.
5. Re-run targeted evaluations (classification accuracy, JSON validity, task success score).
6. Stop and revert if valid response rate drops or retry rate rises materially.

### Phase 4: Evaluate and report

1. Capture optimized usage in the same shape as baseline.
2. Run the savings estimator:

   ```bash
   python skills/eli-token-optimizer/scripts/estimate-token-savings.py \
     --baseline baseline.json --optimized optimized.json \
     --output-json savings.json --output-md savings.md
   ```

3. Compare cost per successful task, not raw token reduction alone.
4. Deliver the report using the template below.

## Report template

```markdown
# Token Optimization Report

## Executive summary
[One paragraph: baseline cost, changes made, net savings, quality impact]

## Baseline metrics
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Input tokens / request | | | |
| Output tokens / request | | | |
| Model calls / task | | | |
| Cost / successful task | | | |
| Valid response rate | | | |
| Retry rate | | | |

## Changes applied
1. [Technique] — [file/area] — expected savings — risk level

## Changes deferred
- [Technique] — reason not applied now

## Risks and monitoring
- Metrics to watch: cache-hit rate, human correction rate, P95 latency
- Rollback triggers: [specific thresholds]

## Next steps
- [Highest-ROI remaining technique]
```

## Safety rules

- Never weaken tenant isolation or permission checks to improve cache hit rate.
- Never cache responses that depend on live user state without freshness rules.
- Never set global output caps that break structured output (JSON, code, citations).
- Change one optimization at a time; keep a control group when traffic allows.
- A 40% token reduction that doubles retries is a failure.

## Reference files

- [references/techniques.md](references/techniques.md) — all 16 techniques with examples and checklists
- [references/implementation-patterns.md](references/implementation-patterns.md) — reusable code patterns
- [references/evaluation-checklist.md](references/evaluation-checklist.md) — metrics and verification steps

## Utility scripts

| Script | Purpose |
|--------|---------|
| `scripts/audit-llm-calls.py` | Scan Python/TS for LLM calls and common waste patterns |
| `scripts/estimate-token-savings.py` | Compare baseline vs optimized usage |

Both scripts are read-only auditors / calculators — they do not modify application code.
