# Agent instructions

This repository ships one skill and its worked example.

- **Skill:** [`skills/implement-slide-tools/SKILL.md`](skills/implement-slide-tools/SKILL.md)
- **Worked example:** `skills/implement-slide-tools/deck.html` — a six-slide deck with the
  picker, multi-picker and PDF export installed.
- **Human docs:** [`README.md`](README.md) and [`docs/`](docs/)

Read the skill file before changing anything in `skills/`. Its code blocks and
`deck.html` are kept in sync on purpose: the guide is what an agent pastes into a
target deck, so a difference between the two is a bug, not a style choice.

To install the skill into a project, copy the folder:

```bash
cp -r skills/implement-slide-tools ~/.claude/skills/     # or your agent's skills dir
```
