# Agent builder

One prompt. Someone pastes [SKILL.md](SKILL.md) into a Claude or ChatGPT chat. ELI introduces itself, you tap Start, then a few multiple-choice questions, personalised from what the chat already knows about them. They answer in taps, not paragraphs. Then it builds three agents for their role, each as a paste-ready prompt with a trigger, inputs, steps, an exact output, guardrails, and a test. It ends with one agent to skip and a card they can forward.

Covers founder, engineering, product, design, sales, marketing, support, finance, ops, people, recruiting, IT, legal, and data. Other roles are adapted from the closest two.

Also installs as a skill: copy this folder to `.claude/skills/agent-builder/` and run `/agent-builder`.

The page to publish is `https://www.eli.work/agent-builder`: this prompt and a copy button. Every card links there.
