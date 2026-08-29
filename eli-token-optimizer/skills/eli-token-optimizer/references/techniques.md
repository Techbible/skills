# Token Optimization Techniques

Sixteen vendor-neutral techniques to reduce AI inference cost. Apply selectively — not every technique fits every workload.

**Cost equation:** `AI cost = input tokens + output tokens + number of model calls × price per token`

---

## 1. Concise output instructions

### Problem it solves
Models often repeat the question, add preambles, explain structure, and close with filler. You pay for every unnecessary output token.

### When to use
FAQs, support replies, summaries, classifications, high-volume internal assistants.

### When not to use
Tasks requiring step-by-step reasoning, safety guidance, legal/medical disclaimers, or teaching contexts where verbosity is the product.

### Python example

```python
SYSTEM = """
Answer directly. Skip the preamble. Do not repeat the question.
Use the fewest words needed for a complete answer.
Lead with the action the user should take.
"""

response = client.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": query}],
    max_tokens=350,
)
```

### TypeScript example

```typescript
const system = `Answer directly. Skip preamble. Lead with the action.
Use the fewest words needed for a complete answer.`;

const response = await client.chat.completions.create({
  model,
  messages: [
    { role: "system", content: system },
    { role: "user", content: query },
  ],
  max_tokens: 350,
});
```

### Quality and security risks
- **Quality:** Answers become too terse; users miss context or reasoning.
- **Security:** Over-compression may omit safety warnings or escalation paths.

### Metrics to track
Output tokens per request, valid response rate, human correction rate, task success score.

### Verification checklist
- [ ] Test tasks needing context, reasoning, and step-by-step instructions
- [ ] Compare output token median before/after
- [ ] Review sample outputs for missing critical information
- [ ] Confirm safety/disclaimer content is preserved where required

---

## 2. Output token budget

### Problem it solves
Instructions alone do not enforce a hard ceiling. Unbounded generation inflates output cost and latency.

### When to use
Any task with predictable answer length: classification, extraction, short replies, structured summaries.

### When not to use
Reports, code generation, multi-section documents, or any task where truncation breaks downstream parsing.

### Python example

```python
LIMITS = {
    "classification": 50,
    "support_reply": 350,
    "summary": 600,
    "report": 2000,
}

def max_output_for(task_type: str) -> int:
    return LIMITS.get(task_type, 500)

request = {
    "model": model,
    "messages": messages,
    "max_tokens": max_output_for(task_type),
}

# Handle truncation
if response.finish_reason == "length":
    return handle_partial(response, retry_with=LIMITS[task_type] * 2)
```

### TypeScript example

```typescript
const LIMITS: Record<string, number> = {
  classification: 50,
  support_reply: 350,
  summary: 600,
  report: 2000,
};

const maxTokens = LIMITS[taskType] ?? 500;

const response = await client.chat.completions.create({
  model,
  messages,
  max_tokens: maxTokens,
});

if (response.choices[0]?.finish_reason === "length") {
  return handlePartial(response, retryWith: maxTokens * 2);
}
```

### Quality and security risks
- **Quality:** Truncated JSON, cut-off code, incomplete instructions cost more to repair than tokens saved.
- **Security:** Truncated policy text may omit compliance language.

### Metrics to track
Output tokens per request, truncation rate, retry rate after truncation, valid JSON/structure rate.

### Verification checklist
- [ ] Per-task-type limits defined (not one global cap)
- [ ] Truncation handling implemented (retry, partial state, or user message)
- [ ] Structured output tasks tested for parse failures
- [ ] Truncation rate monitored in production

---

## 3. Whitespace normalization

### Problem it solves
Copied documents and generated prompts contain repeated spaces, tabs, trailing whitespace, and excessive blank lines that add noise and tokens.

### When to use
Plain-text user input, scraped content, email bodies, and prose-heavy prompts before model calls.

### When not to use
Code blocks, Markdown tables, YAML, poetry, or any format where spacing carries meaning.

### Python example

```python
import re

def normalize_plain_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()

def normalize_prompt_parts(parts: list[str], protected: set[int] | None = None) -> list[str]:
    protected = protected or set()
    return [
        p if i in protected else normalize_plain_text(p)
        for i, p in enumerate(parts)
    ]
```

### TypeScript example

```typescript
function normalizePlainText(text: string): string {
  return text
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n")
    .trim();
}
```

### Quality and security risks
- **Quality:** Low — when scoped to plain prose only.
- **Security:** Normalizing structured payloads could alter checksums or signed content.

### Metrics to track
Input tokens per request (expect small reduction), preprocessing latency.

### Verification checklist
- [ ] Code blocks and tables excluded from normalization
- [ ] Input token count compared on sample corpus
- [ ] No semantic changes in normalized samples

---

## 4. JSON minification for prompts

### Problem it solves
Tool results, API payloads, and config objects reach the model as pretty-printed JSON. Indentation helps humans, not models.

### When to use
Embedding JSON tool results, analytics events, or API responses in prompts.

### When not to use
When engineers rely on formatted JSON in the same string for debugging (keep formatted version in logs separately).

### Python example

```python
import json

def minify_json(raw: str) -> str:
    data = json.loads(raw)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

# Use parser — never regex-strip spaces from JSON strings
prompt_context = minify_json(tool_result_json)
```

### TypeScript example

```typescript
function minifyJson(raw: string): string {
  const data = JSON.parse(raw);
  return JSON.stringify(data);
}

const promptContext = minifyJson(toolResultJson);
```

### Quality and security risks
- **Quality:** Regex-based minification can corrupt string values.
- **Security:** Minified secrets in prompts are still secrets — minify does not redact.

### Metrics to track
Input tokens per request on JSON-heavy workloads.

### Verification checklist
- [ ] Parser-based minification (not regex)
- [ ] Formatted JSON retained in logs for debugging
- [ ] Round-trip parse verified on sample payloads

---

## 5. Collapse duplicate messages

### Problem it solves
Retries, webhooks, agent loops, and middleware bugs append identical messages. Repeated system instructions stack when layers compose requests.

### When to use
Any multi-turn or agent pipeline where duplicate append is possible.

### When not to use
When a user intentionally repeats a request for emphasis or correction — use event/retry IDs for stronger dedup signals.

### Python example

```python
def collapse_consecutive_duplicates(messages: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for message in messages:
        if cleaned and message == cleaned[-1]:
            continue
        cleaned.append(message)
    return cleaned
```

### TypeScript example

```typescript
function collapseConsecutiveDuplicates(
  messages: Array<{ role: string; content: string }>
): typeof messages {
  const cleaned: typeof messages = [];
  for (const message of messages) {
    const prev = cleaned[cleaned.length - 1];
    if (prev && JSON.stringify(prev) === JSON.stringify(message)) continue;
    cleaned.push(message);
  }
  return cleaned;
}
```

### Quality and security risks
- **Quality:** Aggressive cross-conversation dedup may remove intentional repetition.
- **Security:** Low when limited to consecutive exact matches.

### Metrics to track
Input tokens per request, messages array length distribution.

### Verification checklist
- [ ] Only consecutive exact duplicates removed initially
- [ ] Retry/event IDs tracked where available
- [ ] User re-prompt scenarios tested

---

## 6. Trim conversation history

### Problem it solves
Long-running assistants resend full chat every turn. Input cost grows linearly even when middle turns no longer matter.

### When to use
Multi-turn chat, agents with durable goals, support threads with long histories.

### When not to use
Tasks requiring full verbatim history (legal review, audit trails) unless durable state is extracted first.

### Python example

```python
def trim_history(messages: list[dict], recent_turns: int = 6) -> list[dict]:
    system = [m for m in messages if m.get("role") == "system"][:1]
    users = [m for m in messages if m.get("role") == "user"]
    first_user = users[:1]
    recent = messages[-recent_turns:]
    seen = set()
    deduped = []
    for m in system + first_user + recent:
        key = (m.get("role"), m.get("content"))
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    return deduped
```

### TypeScript example

```typescript
function trimHistory(
  messages: ChatMessage[],
  recentTurns = 6
): ChatMessage[] {
  const system = messages.filter((m) => m.role === "system").slice(0, 1);
  const firstUser = messages.filter((m) => m.role === "user").slice(0, 1);
  const recent = messages.slice(-recentTurns);
  return [...system, ...firstUser, ...recent];
}
```

### Quality and security risks
- **Quality:** Deleted turns may contain facts still needed for the answer.
- **Security:** Dropping messages may remove consent or policy acknowledgments.

### Metrics to track
Input tokens per request, task success score on memory-heavy conversations, user correction rate.

### Verification checklist
- [ ] Stable system prompt preserved
- [ ] First user message / goal preserved
- [ ] Durable state extracted to compact JSON where needed
- [ ] Memory-heavy and multi-step agent tasks in eval set

---

## 7. Exact-match caching

### Problem it solves
Identical deterministic requests pay full inference cost on every repeat.

### When to use
FAQ answers, deterministic transforms, document classification, idempotent background jobs with `temperature=0`.

### When not to use
Personalized, time-sensitive, or permission-sensitive responses without proper cache key scoping.

### Python example

```python
import hashlib
import json

def cache_key(tenant_id: str, model: str, prompt_version: str, messages: list, tools: list | None) -> str:
    payload = {
        "tenant_id": tenant_id,
        "model": model,
        "prompt_version": prompt_version,
        "temperature": 0,
        "messages": messages,
        "tools": tools or [],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def cached_completion(cache, tenant_id, model, prompt_version, messages, tools, run_model):
    key = cache_key(tenant_id, model, prompt_version, messages, tools)
    if cache.exists(key):
        return cache.get(key)
    response = run_model(messages)
    cache.set(key, response, ttl=86400)
    return response
```

### TypeScript example

```typescript
import { createHash } from "crypto";

function cacheKey(params: {
  tenantId: string;
  model: string;
  promptVersion: string;
  messages: unknown[];
  tools?: unknown[];
}): string {
  const payload = JSON.stringify({ ...params, temperature: 0 });
  return createHash("sha256").update(payload).digest("hex");
}
```

### Quality and security risks
- **Quality:** Stale answers when product or policy changes without prompt_version bump.
- **Security:** Missing tenant_id or permissions in key causes cross-tenant data leakage.

### Metrics to track
Cache-hit rate, cost per request, stale-answer reports, P50 latency.

### Verification checklist
- [ ] Cache key includes tenant_id, model, prompt_version, tools, temperature
- [ ] TTL and invalidation policy documented
- [ ] Cross-tenant isolation tested
- [ ] prompt_version bumped on policy changes

---

## 8. Stable prompt prefixes

### Problem it solves
Many providers discount repeated prompt prefixes. Volatile data at the top of the prompt prevents prefix cache hits.

### When to use
High-volume workloads with large shared system prompts, tool definitions, or reference docs.

### When not to use
Prompts with no stable prefix (fully dynamic system instructions every request).

### Python example

```python
def build_messages(system: str, tools: str, shared_ref: str, session: str, user_msg: str) -> list[dict]:
    # Stable prefix first; volatile data last
    combined_system = f"{system}\n\n{tools}\n\n{shared_ref}"
    return [
        {"role": "system", "content": combined_system},
        {"role": "system", "content": session},  # session-specific, after stable block
        {"role": "user", "content": user_msg},
    ]
```

### TypeScript example

```typescript
function buildMessages(parts: {
  system: string;
  tools: string;
  sharedRef: string;
  session: string;
  userMsg: string;
}) {
  const stablePrefix = `${parts.system}\n\n${parts.tools}\n\n${parts.sharedRef}`;
  return [
    { role: "system", content: stablePrefix },
    { role: "system", content: parts.session },
    { role: "user", content: parts.userMsg },
  ];
}
```

### Quality and security risks
- **Quality:** None directly — structural change only.
- **Security:** Do not move secrets into the shared prefix if logs expose prefix content.

### Metrics to track
Provider prefix cache-hit rate (if exposed), input token cost per request.

### Verification checklist
- [ ] Timestamps and request IDs moved after stable prefix
- [ ] User-specific values not in first 1k tokens of shared block
- [ ] Cache-hit rate tracked by model and prompt_version

---

## 9. Semantic caching

### Problem it solves
Exact caches miss paraphrased questions with the same intent ("cancel plan" vs "end subscription").

### When to use
Stable support and knowledge-base questions with fresh, permission-scoped answers.

### When not to use
Personal advice, live data, security-sensitive answers, or queries where small wording changes alter the required response.

### Python example

```python
def semantic_lookup(vector_store, query: str, tenant_id: str, threshold: float = 0.94):
    query_vector = embed(query)
    match = vector_store.search(query_vector, tenant_id=tenant_id, limit=1)
    if match and match.score > threshold and match.metadata.get("fresh"):
        return match.answer
    return None

def answer_with_semantic_cache(vector_store, query, tenant_id, run_model):
    cached = semantic_lookup(vector_store, query, tenant_id)
    if cached:
        return cached
    answer = run_model(query)
    vector_store.save(embed(query), answer, tenant_id=tenant_id)
    return answer
```

### TypeScript example

```typescript
async function semanticLookup(
  store: VectorStore,
  query: string,
  tenantId: string,
  threshold = 0.94
): Promise<string | null> {
  const vector = await embed(query);
  const [match] = await store.search(vector, { tenantId, limit: 1 });
  if (match && match.score > threshold && match.metadata.fresh) {
    return match.answer;
  }
  return null;
}
```

### Quality and security risks
- **Quality:** Similarity threshold too low returns wrong answers for near-miss queries.
- **Security:** Must scope by tenant, permissions, product version, and answer expiry.

### Metrics to track
Semantic cache-hit rate, wrong-answer rate (human corrections), similarity score distribution.

### Verification checklist
- [ ] Eligibility rules include tenant, permissions, language, product version
- [ ] Answer freshness / TTL enforced
- [ ] Near-miss failure cases in eval set
- [ ] Threshold tuned on held-out queries

---

## 10. Model routing

### Problem it solves
Every request hits the most expensive model even when a cheaper model suffices for classification, extraction, or formatting.

### When to use
Mixed workloads with clear task classes and measurable quality per route.

### When not to use
When task complexity cannot be classified reliably from metadata alone without quality regression.

### Python example

```python
def choose_model(task) -> str:
    if task.type in {"classification", "extraction", "formatting"}:
        return "economy-model"
    if task.has_code or task.requires_multi_step_reasoning:
        return "frontier-model"
    if task.risk in {"legal", "medical", "financial", "security"}:
        return "frontier-model"
    return "balanced-model"

def run_with_fallback(task, messages):
    model = choose_model(task)
    response = run_model(model, messages)
    if not passes_quality_gate(response, task):
        return run_model("frontier-model", messages)
    return response
```

### TypeScript example

```typescript
function chooseModel(task: TaskSpec): string {
  if (["classification", "extraction", "formatting"].includes(task.type)) {
    return "economy-model";
  }
  if (task.hasCode || task.requiresMultiStepReasoning) return "frontier-model";
  if (["legal", "medical", "financial", "security"].includes(task.risk)) {
    return "frontier-model";
  }
  return "balanced-model";
}
```

### Quality and security risks
- **Quality:** "Short" confused with "simple" — five-word security requests need strong models.
- **Security:** High-risk categories must never route to economy tier without explicit approval.

### Metrics to track
Cost per task by route, fallback rate, task success score per route, invalid structure rate.

### Verification checklist
- [ ] Test set built from real traffic per route
- [ ] Fallback on low confidence or invalid structure
- [ ] High-risk task classes hard-routed to strongest model
- [ ] Cost and quality compared per route

---

## 11. Batch processing

### Problem it solves
Real-time inference pricing applies to workloads that do not need sub-second answers: evals, enrichment, tagging, embeddings, nightly summaries.

### When to use
Offline or async pipelines with acceptable completion windows (minutes to hours).

### When not to use
Interactive product flows where users wait for the response.

### Python example

```python
def submit_batch(jobs: list[dict], batch_service) -> str:
    return batch_service.submit(jobs)

def collect_and_reconcile(batch_id: str, batch_service, downstream) -> None:
    results = batch_service.collect(batch_id)
    by_id = {r["id"]: r for r in results}
    for job in downstream.pending(batch_id):
        result = by_id.get(job["id"])
        if result:
            downstream.apply(job, result)
```

### TypeScript example

```typescript
async function runBatch(jobs: BatchJob[], service: BatchService) {
  const batchId = await service.submit(jobs);
  const results = await service.collect(batchId);
  const byId = new Map(results.map((r) => [r.id, r]));
  for (const job of jobs) {
    const result = byId.get(job.id);
    if (result) await applyResult(job, result);
  }
}
```

### Quality and security risks
- **Quality:** Delayed results may use stale prompt versions if not versioned per job.
- **Security:** Batch files may aggregate sensitive data — encrypt at rest, scope access.

### Metrics to track
Cost per row, batch completion time, retry/reconcile rate, idempotency violations.

### Verification checklist
- [ ] Request IDs, prompt versions, row IDs stored per job
- [ ] Idempotent retry logic
- [ ] Interactive flows excluded from batch path
- [ ] Reconciliation tested for partial failures

---

## 12. Lower-priority service tier

### Problem it solves
Some providers offer cheaper compute for traffic that tolerates variable latency or temporary unavailability.

### When to use
Development, evaluations, enrichment, offline analysis, low-priority agent jobs.

### When not to use
Strict real-time flows where users abandon before the answer arrives.

### Python example

```python
def run_with_tier(request: dict, tier: str = "standard"):
    request["service_tier"] = tier  # provider-specific field name
    try:
        return provider.complete(request, timeout=90 if tier == "flex" else 30)
    except CapacityUnavailable:
        if tier == "flex":
            queue_for_later(request)
        raise
```

### TypeScript example

```typescript
async function completeWithTier(
  request: CompletionRequest,
  tier: "standard" | "flex" = "standard"
) {
  try {
    return await provider.complete({ ...request, serviceTier: tier });
  } catch (err) {
    if (tier === "flex" && isCapacityError(err)) {
      await queueForLater(request);
    }
    throw err;
  }
}
```

### Quality and security risks
- **Quality:** Timeouts cause incomplete tasks if no fallback.
- **Security:** None specific — same data handling as standard tier.

### Metrics to track
Cost per job, timeout rate, queue depth, user abandonment (for any user-facing use).

### Verification checklist
- [ ] Timeout and fallback policy defined
- [ ] Real-time flows stay on standard tier
- [ ] Capacity errors handled without silent drops

---

## 13. RAG context pruning

### Problem it solves
RAG pipelines retrieve many long documents and send all passages to the generator. Much retrieved text does not answer the question.

### When to use
RAG systems with high retrieval top_k and measurable answer quality evals.

### When not to use
When retrieval already returns minimal, highly relevant chunks and pruning would drop evidence.

### Python example

```python
def pruned_rag(query: str, retriever, reranker, threshold: float = 0.5, max_passages: int = 8):
    documents = retriever.retrieve(query, top_k=20)
    passages = split_into_passages(documents)
    ranked = reranker.rank(query, passages)
    selected = [p for p in ranked if p.score > threshold][:max_passages]
    if not selected:
        return generate_no_answer(query)
    return generate(query=query, context=selected)
```

### TypeScript example

```typescript
async function prunedRag(
  query: string,
  retriever: Retriever,
  reranker: Reranker,
  threshold = 0.5,
  maxPassages = 8
) {
  const docs = await retriever.retrieve(query, { topK: 20 });
  const passages = splitIntoPassages(docs);
  const ranked = await reranker.rank(query, passages);
  const selected = ranked.filter((p) => p.score > threshold).slice(0, maxPassages);
  if (selected.length === 0) return generateNoAnswer(query);
  return generate({ query, context: selected });
}
```

### Quality and security risks
- **Quality:** Pruning drops evidence needed for correct cited answers.
- **Security:** Pruned context must not bypass document-level access controls applied at retrieval.

### Metrics to track
Input tokens per RAG request, answer recall, citation accuracy, "no answer" rate.

### Verification checklist
- [ ] Answer recall measured, not just token reduction
- [ ] "No answer in context" path when evidence is weak
- [ ] Citations verified against retained passages
- [ ] Document permissions enforced before pruning

---

## 14. Prompt compression (smaller model)

### Problem it solves
Long documents, transcripts, and retrieved context dominate input tokens. A smaller compression step can reduce context before the main model call.

Optional open-source tools such as **LLMLingua-2** follow this pattern.

### When to use
Large context windows where compression savings exceed the extra compression call cost.

### When not to use
Short contexts where compression overhead exceeds savings, or tasks where every token carries legal/medical significance.

### Python example

```python
def compress_and_answer(compressor, main_model, long_context: str, query: str, target_ratio: float = 0.4):
    compressed = compressor.compress(
        context=long_context,
        query=query,
        target_ratio=target_ratio,
    )
    return main_model.generate(query=query, context=compressed)
```

### TypeScript example

```typescript
async function compressAndAnswer(
  compressor: Compressor,
  mainModel: Model,
  longContext: string,
  query: string,
  targetRatio = 0.4
) {
  const compressed = await compressor.compress({
    context: longContext,
    query,
    targetRatio,
  });
  return mainModel.generate({ query, context: compressed });
}
```

### Quality and security risks
- **Quality:** Numbers, names, negations, and dates disappear first under aggressive compression.
- **Security:** Compression must not strip access-control markers or redaction tags.

### Metrics to track
Input tokens before/after compression, compression latency, task success on edge-case eval set.

### Verification checklist
- [ ] Eval set includes numbers, dates, negations, proper nouns
- [ ] Compression cost + main call < uncompressed main call
- [ ] Compression ratio tuned per workload

---

## 15. Evaluation-driven prompt optimization

### Problem it solves
Suboptimal prompts cause retries, low first-pass success, and over-reliance on expensive models. Systematic prompt iteration improves efficiency indirectly.

Optional frameworks such as **GEPA** automate variant testing against graders.

### When to use
Mature, repeatable workflows with reliable graders and stable task definitions.

### When not to use
Early prototypes whose task definition changes weekly.

### Python example

```python
def optimize_prompt(current_prompt: str, train: list, val: list, rounds: int = 5) -> str:
    baseline = current_prompt
    for _ in range(rounds):
        failures = evaluate(baseline, train)
        candidates = propose_edits(baseline, failures)
        baseline = select_best(candidates, val)
    return baseline

# Always evaluate on held-out test set before shipping
final_score = evaluate(baseline, held_out_test)
```

### TypeScript example

```typescript
async function optimizePrompt(
  current: string,
  train: Example[],
  val: Example[],
  rounds = 5
): Promise<string> {
  let baseline = current;
  for (let i = 0; i < rounds; i++) {
    const failures = await evaluate(baseline, train);
    const candidates = proposeEdits(baseline, failures);
    baseline = await selectBest(candidates, val);
  }
  return baseline;
}
```

### Quality and security risks
- **Quality:** Overfitting to training examples; poor generalization on live traffic.
- **Security:** Optimizer may strip safety instructions to maximize task score — guard rails required.

### Metrics to track
Task success score, retry rate, cost per successful task, held-out test performance.

### Verification checklist
- [ ] Separate train / validation / held-out test sets
- [ ] Safety instructions included in non-negotiable prompt sections
- [ ] Held-out test run before production deploy
- [ ] Cost per successful task compared, not just accuracy

---

## 16. Compact reasoning format

### Problem it solves
Long chain-of-thought traces consume output tokens. Compact sketches (keywords, symbols, short phrases) reduce reasoning overhead.

### When to use
Math, planning, and multi-hop tasks where intermediate prose is expensive and final answer is verifiable.

### When not to use
Tasks requiring auditable reasoning trails (compliance, education, debugging agent failures).

### Python example

```python
REASONING_SYSTEM = """
Solve using a compact reasoning sketch.
Use short phrases and symbols for intermediate steps.
Return JSON: {"sketch": [...], "answer": "..."}
Minimum explanation needed to verify the answer.
"""

response = run_model(messages=[
    {"role": "system", "content": REASONING_SYSTEM},
    {"role": "user", "content": problem},
])
```

### TypeScript example

```typescript
const reasoningSystem = `
Solve using a compact reasoning sketch.
Use short phrases and symbols for intermediate steps.
Return JSON: {"sketch": string[], "answer": string}
`;

const response = await runModel([
  { role: "system", content: reasoningSystem },
  { role: "user", content: problem },
]);
```

### Quality and security risks
- **Quality:** Over-compression lowers accuracy; mistakes harder to inspect.
- **Security:** Opaque reasoning hides harmful or policy-violating intermediate steps.

### Metrics to track
Output tokens per task, accuracy on reasoning eval set, human review time for failures.

### Verification checklist
- [ ] Accuracy tested across models and languages
- [ ] Structured sketch format parseable for debugging
- [ ] Compliance tasks excluded from compact reasoning

---

## Application phases

| Phase | Techniques | Infrastructure |
|-------|------------|----------------|
| 1 — Quick wins | 1–5 | Minimal |
| 2 — Context/calls | 6–8 | Low |
| 3 — Traffic | 9–12 | Medium |
| 4 — Advanced | 13–16 | Higher |

Change one technique at a time. A technique that cuts tokens 40% but doubles retries has failed.
