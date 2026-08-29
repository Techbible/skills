# Techbible Skills

Claude Code skills, one folder each. Install: copy a folder into your repo's `.claude/skills/` (or `~/.claude/skills/`), start a new session, invoke with `/<name>`.

| Skill | What it does |
|-------|--------------|
| [`connector-factory`](connector-factory/) | Builds vendor API integrations end to end with parallel agents: doc-verified capability research, implementation in isolated worktrees, adversarial review, live key verification, human setup checklist. Run research-only to get a per-vendor capability matrix. |
| [`agent-context-docs`](agent-context-docs/) | Interactively builds the ten context documents a company's AI agents need before deployment. Asks sharp questions, drafts each doc with the user's real details, refines in a loop. |
| [`eli-token-optimizer`](eli-token-optimizer/) | Audits AI applications for token waste and inference cost, ranks optimizations by savings and risk, and measures cost per successful task. Includes vendor-neutral guidance and standard-library audit tools. |
