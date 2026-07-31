# Live verification, mutation safety, and universal vendor-API pitfalls

## Live testing pattern (after local commit, before any push)

Test the connector layer directly with the user's real keys, calling it exactly the way the sync layer does (same entry point, same argument shapes) via a throwaway script - never committed, never logging full keys.

Order of testing:
1. **Reads first.** Zeros on a fresh account are a PASS - check shapes, not values.
2. **Error paths deliberately.** Wrong-scope key, personal vs organization account, suspended/unpaid account. A clean actionable error message is a feature; a crash is a bug. These paths WILL be hit by real customers.
3. **Full product flow.** The user connects through the real UI (credential save -> verify -> sync -> record created), then any assistant/agent surface on top.
4. **Mutations last**, only with the rules below.

## Mutation safety rules

- Only run mutations the user asked to verify, on THEIR OWN test accounts.
- Prefer fully reversible chains: create a disposable identity (user+test@domain) at the LOWEST role, verify it appears, change its role, revert.
- Never demote or remove: the identity that owns the API key in use, the account owner, or the last admin (lockout risk).
- If the vendor has no delete API, say up front that cleanup is a console step.
- Vendors are eventually consistent: a failed revert may succeed on retry - retry once before reporting failure.
- One account per vendor is enough; a second account adds nothing but cost.

## Universal vendor-API pitfalls (every one caught as a real bug - check each on every new vendor)

- **End-EXCLUSIVE date params.** Some vendors treat the end date as exclusive and date-only: send the next UTC midnight after your period end or you silently drop the current day from usage and spend.
- **UTC vs local month starts.** Build month windows with UTC constructors end to end; mixing local-time starts with UTC filters reports zero spend in UTC+ timezones on the 1st of the month.
- **History horizons.** APIs that expose only the last N days cannot answer "previous month" most of the time. Reject or clamp out-of-horizon windows HONESTLY (explicit error the sync treats as a warning) instead of returning a silently understated number.
- **Lifetime vs windowed billing.** Credit/balance endpoints are usually lifetime totals; never present them as monthly spend. Compute windows from activity feeds and label the semantics.
- **Batched writes sink whole batches.** One ineligible item (e.g. a seat assigned via a group/team) can 422 an entire batch call; filter ineligible items before batching.
- **Rosters may not exist.** Usage-only platforms have no members API; derive best-effort rosters (key creators, usage attribution) and label the roles honestly (usage-only, key-creator) instead of pretending they are directory users.
- **"Not enabled" is ambiguous with "no permission."** 403/422 often covers both "org does not have the product" and "token lacks a scope/role"; skip-reasons must state both and the remedy.
- **Suspended accounts pass auth.** The key authenticates, then every data call fails with a suspension notice - surface the vendor's message verbatim with their billing URL.
- **Role catalogs differ per account/tier.** A role that exists in docs may be disabled on a given account; map roles but pass vendor errors through readably.
- **Tier-gated endpoints.** Most customers sit BELOW the gate (enterprise-only member APIs, paid analytics): degrade to what works (often billing) instead of erroring - the degraded state is the common state.
- **Docs may be bot-blocked.** Fall back to probing the live API (401 vs 404 tells you a route exists) and cross-checking several independent open-source clients; record which claims are spec-verified vs inferred.

## Hand-off template (what the user gets at the end)

1. Honest scorecard per vendor: reads / mutations / error paths / product flow, each marked live-verified, unit-tested-only, or impossible-without-X (and why that is acceptable).
2. Manual setup checklist: exact console path to create each credential, trap flags, plan requirements, and for derived connectors the full consent chain (scope push -> console -> re-consent).
3. What remains unverified and the exact signal that will complete verification later (e.g. "first customer with the product connected - watch the sync logs for X").
4. The waiting local commits and the explicit statement that nothing was pushed.
