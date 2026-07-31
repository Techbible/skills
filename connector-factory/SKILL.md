---
name: connector-factory
description: Build vendor API connectors/integrations end to end with parallel agents - live-docs research, implementation in isolated git worktrees, adversarial review, merge, verification with real keys, and a human setup checklist. Also usable research-only to produce a vendor capability matrix. Use for adding SaaS or AI vendor integrations, or for auditing what a vendor's API actually allows per plan tier.
argument-hint: [vendor names, e.g. "deepgram elevenlabs" or "research-only stripe zoom"]
disable-model-invocation: true
---

# Connector Factory

A multi-agent pipeline for shipping vendor API integrations - or, run research-only, for producing an accurate per-vendor capability matrix. Battle-tested on a production SaaS-spend product: across the first eight connectors built this way, the adversarial review stage caught twelve real bugs the implementers and their tests missed, including two classes that silently corrupt money data.

Follow the stages in order. Do not skip review or the duplicate-list sweep; every rule in this file corresponds to a bug that actually happened.

Reference files (read on demand, not upfront):
- [references/agent-prompts.md](references/agent-prompts.md) - prompt templates for research, implementation, review, and merge agents
- [references/wiring-guide.md](references/wiring-guide.md) - the generic integration checklist and how to derive your project-specific one
- [references/verification.md](references/verification.md) - live testing patterns, mutation safety rules, and universal vendor-API pitfalls

## Hard rules

1. NEVER push or open a PR unless the user explicitly says so in this session. Commit locally and stop.
2. Sub-agents (implementers, reviewers, mergers) leave changes UNCOMMITTED; only the main agent commits, after its own verification pass.
3. Any API key the user pastes into chat is exposed; remind them to rotate it after testing.
4. Update the project's canonical integration docs in the same commit/PR as the connector (find where the project documents its integrations; if nowhere, flag that).
5. Before declaring a test failure "new", check it against the clean tree (`git stash` and re-run); most repos carry known pre-existing failures.

## Model selection per stage

Use tiers, mapped to whatever models are available (fast = Haiku-class, balanced = Sonnet-class, top = Opus/Fable-class):

| Stage | Tier | Rationale |
|-------|------|-----------|
| Research | balanced | Doc reading + structured extraction; fast tier misses plan-gating nuances |
| Implementation | balanced for pattern-clones; top for the first connector of a new pattern | The adversarial review is the quality gate, so clones do not need the top model |
| Adversarial review | top, always | Empirically where all real bugs are caught; never downgrade this stage |
| Merge | balanced (top when merging more than 3 parallel branches) | Mechanical when given a precise conflict map |
| Docs/catalog updates | fast | Config rows and doc tables |

## Stage 0: Intake

1. Check whether vendor research already exists in the project (search docs/ for capability matrices) - skip Stage 1 if fresh.
2. Sync: `git fetch origin`, fast-forward the base branch, create ONE feature branch for the whole batch.
3. Decide transport per vendor:
   - Vendor data reachable through an OAuth connection the product ALREADY holds (e.g. a GitHub or Google connection)? -> **derived connector**: extra vendor riding the parent connection. Budget for scope additions and customer re-consent.
   - Vendor offers an admin/management API key? -> **native key connector**: customer pastes a key; simplest transport.
   - Neither -> STOP. The vendor is detection-only (receipts, card feeds). Building a connector is impossible at any effort level; record that verdict so nobody re-litigates it.

## Stage 1: Research (also the whole pipeline in research-only mode)

Spawn one background research agent per 3-4 vendors, balanced tier, using the research template in [references/agent-prompts.md](references/agent-prompts.md). Non-negotiables:
- Verify against LIVE official docs, never from memory; require a doc URL for every claim.
- Grade every capability per method as Working (standard plan) / Paid unlock (name the tier and price) / Unreachable (no API at any tier).
- Capture per-method granularity for usage data (per user? per API key? per model?) - it determines the product features the connector can power.
- Record the auth method a third party would actually use, and any middleware/aggregator catalog coverage.

If the user asked for research only: consolidate into a capability matrix (CSV mirroring their existing tracking format if they have one), deliver, stop.

## Stage 2: Implementation (parallel)

One agent per connector. First connector in the MAIN tree; every additional one in an isolated git worktree (they will all touch the same shared registry/config files - Stage 4 unifies). Use the implementation template. Non-negotiables baked into it:
- Re-verify every endpoint and scope against live docs BEFORE coding; if docs are bot-blocked, probe the live API and cross-check multiple independent open-source clients, and say so.
- Follow the project's existing connector contract exactly; unsupported methods fail explicitly with the vendor's console URL, never silently.
- Never fake data: null/absent over invented zeros; degraded tiers degrade gracefully instead of erroring.
- Complete the project wiring checklist (see [references/wiring-guide.md](references/wiring-guide.md)).
- Mocked-HTTP unit tests covering failure modes, not just happy paths; all relevant suites green.
- No commits; report decisions, verified facts, test results, and anything unverifiable without a live account.

## Stage 3: Adversarial review (one reviewer per connector, top tier)

Spawn each reviewer the moment its implementation lands, pointed at that connector's tree/worktree, using the review template. The reviewer fixes clearly-correct local issues and re-runs tests; reports anything architectural. Priority attack list (each item has caught a real production-grade bug):

1. Date/window math: UTC vs local, end-EXCLUSIVE date params, month boundaries, API history horizons vs the sync's requested windows.
2. Cross-tenant credential contamination: stateful connector instances must never enter shared caches.
3. Silent-skip/degradation gates that could mask real auth failures.
4. Schema enum completeness on every write path (a missing enum value often fails silently).
5. Entity-identity dedupe: can the new vendor's record merge into an existing one (domain roots, fuzzy name containment)?
6. Duplicate vendor lists ("twin lists") anywhere in the codebase that must include the new vendor or money double-counts.
7. Pagination termination, error-class mapping, money parsing edge cases (string int64, negative components).
8. Independent re-verification of endpoint/scope facts against official docs.
9. Test quality: add missing failure-mode tests.

## Stage 4: Merge (only when more than one connector was built)

One merge agent in the main tree after ALL reviews pass, fed every reviewer's shared-file conflict map plus the unification rules in the merge template: one code path for shared logic (extend helpers, never re-inline), enum unions only, no field or helper defined twice, twin lists completed for ALL new vendors. Verify every worktree file is accounted for; full test suite with zero NEW failures. Remove worktrees after porting.

## Stage 5: Main-agent verification and local commit

1. Re-run the connector and contract suites yourself; spot-check the diff.
2. Commit locally in the project's commit style. Do NOT push (hard rule 1).
3. Live verification with the user's real keys per [references/verification.md](references/verification.md): reads first, error paths deliberately (they are product surface), then reversible mutations only, with the mutation safety rules.

## Stage 6: Hand-off

One message to the user: honest scorecard (what was live-verified, what could not be and why), the manual setup checklist (exact console paths for key creation per vendor; scopes/re-consent chain for derived connectors), and the waiting local commits. Then STOP - push/PR only on explicit instruction.
