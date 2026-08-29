# Eli Token Optimizer

An open-source agent skill from [Eli](https://eli.work) for reducing AI token usage and inference costs.

Eli Token Optimizer helps coding agents inspect LLM call sites, rank optimization techniques by savings and risk, apply low-risk changes first, and measure **cost per successful task** — not raw token counts alone.

## What it does

- Scans Python and TypeScript codebases for model API calls, prompt builders, and common waste patterns
- Guides agents through 16 vendor-neutral optimization techniques (caching, routing, RAG pruning, output budgets, and more)
- Establishes cost/quality baselines before changes
- Ranks optimizations by expected savings, engineering effort, and quality risk
- Produces audit and savings reports with actionable next steps

## Who it is for

- Engineering teams running LLM features in production
- Developers building agents, RAG pipelines, or chat products
- Anyone asked to "reduce AI costs" without blindly switching to a weaker model
- Cursor users who want automatic skill invocation when cost optimization comes up

## Installation

### Option A: Install as a Cursor Agent Plugin (recommended)

1. Clone or copy this repository:

   ```bash
   git clone https://github.com/your-org/eli-token-optimizer.git
   ```

2. In Cursor, install the plugin from the local folder or GitHub URL (Agent Plugins → Add plugin).

3. Cursor loads skills from the `skills/` directory declared in `plugin.json`.

### Option B: Copy the skill into your project

Place the skill folder at either location:

```
.cursor/skills/eli-token-optimizer/
```

or

```
.agents/skills/eli-token-optimizer/
```

Copy the contents of `skills/eli-token-optimizer/` (including `SKILL.md`, `references/`, and `scripts/`).

### Option C: Personal skill (all projects)

```bash
cp -r skills/eli-token-optimizer ~/.cursor/skills/eli-token-optimizer
```

## Automatic invocation

This skill has **automatic model invocation enabled** (no `disable-model-invocation: true` in frontmatter).

Cursor reads each skill's `description` field and matches it against your request. When you mention LLM costs, token usage, prompt optimization, caching, model routing, RAG context, agent loops, or similar terms, the agent loads Eli Token Optimizer and follows its workflow.

## Manual invocation

Type the skill name as a slash command:

```
/eli-token-optimizer
```

Or reference it explicitly:

```
Use the eli-token-optimizer skill to audit our backend for token waste.
```

## Example prompts

**Should trigger automatic invocation:**

1. "Our OpenAI bill doubled last month — find where we're wasting tokens."
2. "Audit this codebase for missing max_tokens limits and unbounded chat history."
3. "How can we reduce inference costs on our RAG pipeline without hurting answer quality?"
4. "We're calling GPT-4 on every request — help me add model routing."
5. "Add semantic caching for our support bot and measure the savings."

**Should not trigger:**

1. "Fix the CSS layout on the pricing page."
2. "Write unit tests for the Stripe webhook handler."
3. "Explain how React Server Components work."

## Scripts

### Audit LLM calls (read-only)

```bash
python skills/eli-token-optimizer/scripts/audit-llm-calls.py /path/to/project --output audit-report.md
```

Flags missing output limits, repeated prompts, unbounded history patterns, and hard-coded expensive models.

### Estimate savings

```bash
python skills/eli-token-optimizer/scripts/estimate-token-savings.py \
  --baseline baseline.json \
  --optimized optimized.json \
  --output-json savings.json \
  --output-md savings.md
```

JSON/CSV input fields: `input_tokens_per_request`, `output_tokens_per_request`, `requests`, `cost_usd`, `successful_tasks` (required); `retries`, `attempts`, and quality metrics (optional).

### Run tests

```bash
python -m unittest discover -s skills/eli-token-optimizer/tests -v
```

## Repository structure

```
eli-token-optimizer/
├── plugin.json
├── README.md
├── LICENSE
└── skills/
    └── eli-token-optimizer/
        ├── SKILL.md
        ├── references/
        │   ├── techniques.md
        │   ├── implementation-patterns.md
        │   └── evaluation-checklist.md
        └── scripts/
            ├── audit-llm-calls.py
            └── estimate-token-savings.py
```

## Limitations

- The audit script uses pattern matching — it will miss dynamically constructed calls, config-only model names, or custom SDK wrappers.
- Token savings estimates require accurate usage data from logs or billing exports.
- Optimization recommendations are guidance; always validate quality on your eval set.
- Semantic caching, batch APIs, and compression require infrastructure this skill does not deploy.

## Safety considerations

- Never weaken tenant isolation or permission checks to improve cache hit rate.
- Include `tenant_id`, `prompt_version`, and permission scope in cache keys.
- Change one optimization at a time and monitor retry rate and valid response rate.
- A large token reduction that doubles retries is a net failure.

## Links

- [Eli](https://eli.work) — AI workspace and agent tooling
- MIT License — see [LICENSE](LICENSE)

## Contributing

Issues and pull requests welcome. Keep the skill vendor-neutral: techniques should apply across OpenAI, Anthropic, Google, open-source models, and other providers.
