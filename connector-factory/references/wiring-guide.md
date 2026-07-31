# Wiring guide: the generic integration checklist

Every codebase that integrates vendors has the same categories of wiring, under different file names. The FIRST time you use this skill in a project, derive the project-specific checklist (map each category below to actual paths), save it in the project (e.g. `.claude/skills/connector-factory-project.md` or the project docs), and reference it from every implementation prompt. Subsequent runs reuse it.

## Category checklist (map each to your project)

1. **Connector implementation + registry.** The class/module implementing the vendor, and the registry/factory that makes it discoverable. Convention to copy: unsupported methods fail explicitly with the vendor's console URL - never silently.
2. **Credential storage.** Where per-tenant keys/tokens live (encrypted), including per-vendor extra config (tenant ids, account ids, region). Rule: a connector instance holding a credential must NEVER be shared across tenants - check how the registry caches instances.
3. **Sync layer.** The service that calls connector methods on a schedule and persists results. Know exactly what shapes it consumes (billing windows, rosters, usage metrics) and how it treats partial failures (warning vs hard fail vs skip).
4. **Data model enums.** Most schemas gate vendor identifiers with enums (invoice sources, provenance kinds, credential vendors). A missing enum value often fails SILENTLY on save. Find every enum; extend all of them.
5. **Entity identity / dedupe.** Whatever logic decides "is this vendor row the same as an existing row" (domain matching, name fuzz). Prove the new vendor cannot merge into a sibling (e.g. a "GitHub Copilot" row into "GitHub") and that user-created rows get adopted, not duplicated.
6. **Twin lists.** Grep for an existing sibling vendor (e.g. the vendor you copied the connector from) across the WHOLE codebase. Every hit that is a hardcoded vendor list - spend fusion rules, KPI calculators, receipt dedupers, merge guards, frontend presentation maps - must gain the new vendor, or money data double-counts. This is the most commonly missed category and the most expensive when missed.
7. **User-facing catalog.** Frontend/API catalog entries: display name, category, capability tags, auth type, key-help URL, icon. Plus any "connectable" allowlists.
8. **Assistant/agent vocabulary.** If the product has an AI assistant or command layer that names vendors (aliases, pattern matchers, skill resolvers), add the vendor. Pattern-order matters: more specific names before broader ones ("openrouter" before "openai").
9. **Canonical docs.** Wherever the project documents its integrations (capability matrix, connector table, registry count) - update in the same commit/PR.
10. **Tests.** Unit tests for the connector; contract tests if the project has a registry-iterating suite; wiring tests asserting the registry/catalog entries exist.

## Derived connectors (vendor rides an existing OAuth connection)

Extra categories when the new vendor reuses a parent connection (e.g. a Copilot product on a GitHub connection, an AI add-on on a Google Workspace connection):

- **Derived-vendor registry**: a map from parent provider to derived vendor, driving both sync fan-out and UI rows. Keep it meta-driven, single source of truth.
- **Skip semantics**: orgs without the product return an explicit skip (ok + skipped + reason), before any DB write, never masking parent-sync failures. Ambiguous 403s (could be "not enabled" OR "missing scope") must say both and name the re-consent remedy.
- **Scope additions**: request the UNION of live scopes plus new ones - fetch the live OAuth app config first; never overwrite a scope list blind (dropping a live scope breaks unrelated features).
- **The consent chain**: scope config update -> provider console changes (enable APIs, consent-screen scopes, verification for sensitive scopes on external apps) -> every existing connection must RE-CONSENT before the derived sync can read anything. Until then it should skip silently by design.
- **Disconnect guard**: the derived row cannot be disconnected on its own; point at the parent connection.

## Native key connectors

- Ask the vendor for the least-privileged credential that covers the needed reads (management keys that cannot spend, read-only scopes). Document exactly where the customer creates it, with the trap flags ("scope must be Admin, not API", "role is fixed at creation").
- If the API cannot self-discover the tenant (account id, org slug, region), add a credential config field and pin it across key rotations.
