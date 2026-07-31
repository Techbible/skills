# connector-factory

Claude Code skill that builds vendor API integrations end to end, or runs research-only to produce a doc-verified capability matrix.

```
/connector-factory deepgram elevenlabs          # research, build, review, verify
/connector-factory research-only stripe zoom    # capability matrix only
```

Pipeline: research agents grade every vendor capability (Working / Paid unlock / Unreachable) against live docs, implementers build one connector each in isolated git worktrees, a top-tier reviewer per connector attacks the known bug classes (date math, cross-tenant leaks, silent failures, dedupe, duplicate vendor lists), a merge agent unifies, then live verification with real keys. Never pushes or opens PRs without explicit instruction.

First run in a new project: the skill derives a project-specific wiring checklist from the ten generic categories in `references/wiring-guide.md` and saves it in your repo for reuse.

Model tiers are staged for cost: balanced for research and implementation, top only for review, fast for docs. Details in `SKILL.md`.

Extracted from a production spend-management codebase after shipping 8 connectors this way. The pitfalls in `references/verification.md` are real bugs the review stage caught.
