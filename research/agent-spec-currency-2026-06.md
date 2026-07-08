# Agent/skill spec currency check — June 2026

**Date:** 2026-06-19. **Method:** claude-code-guide research agent over the official docs
(sub-agents.md, skills.md, changelog, best-practices) + direct WebFetch verification of the
disputed field table. **Supersedes the agent-side field list in**
`research/agent-skill-spec-ground-truth-MIT-410.md` (the skill-side list there is still current).

## Verdict: is our subagent usage obsolete?

**No — the architecture is current. One field was genuinely broken; everything else was
cosmetic debt that the spec grew to legalize.**

| Our pattern | Verdict | Basis |
|---|---|---|
| Symlink installs → `~/.claude/agents/` + project `.claude/agents/` | **Current.** Symlinks explicitly supported; project scope scanned recursively (v2.1.178). | sub-agents.md "Choose the subagent scope" |
| `agent.manifest.yaml` | **Fine — it's derived, not canonical.** Claude Code routes on filesystem discovery + descriptions; the manifest only feeds `/staff suggest`. Keep it labeled as staff metadata, never as the loader's source of truth. | sub-agents.md discovery order |
| `scope:` inc extension | **Fine.** Not spec, but consumed by `install.sh` and carved out in the validator. Unrelated to the official `isolation`/`permissionMode` fields. | — |
| Description style (~1.4k chars, "Fires on:" + "Anti-scope:") | **Current.** No documented cap for *agent* descriptions; routing is description-based, unchanged. Optional adoption: "use proactively" phrasing signals automatic delegation. | sub-agents.md "Understand automatic delegation" |
| Skills validator + SKILL.md conventions | **Current.** Skill frontmatter spec unchanged vs our validator (1536 combined cap, disable-model-invocation, etc.). | skills.md "Frontmatter reference" |
| **`allowed-tools:` on 22 agents (MIT-433)** | **BROKEN — was silently inert.** The agent spec's tool fields are `tools` (allowlist) / `disallowedTools` (denylist, camelCase); `allowed-tools` is a skills-only field the agent loader ignores. Our least-privilege restrictions never took effect. **Fixed in this PR** (renamed to `tools:` ×22). | sub-agents.md "Available tools", verified verbatim |

## What changed in the spec since the MIT-410 snapshot (early June)

Current agent frontmatter (16 fields, verified verbatim from sub-agents.md):
`name`\*, `description`\*, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`,
`skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`,
`initialPrompt`.

- **`tools` / `disallowedTools`** replaced the MIT-410-era `allowed-tools`/`disallowed-tools`
  on agents (those names remain correct *for skills*). This inverted MIT-412's premise —
  the field we swept out is now the right one.
- **`color` is now official** (enum: red, blue, green, yellow, purple, orange, pink, cyan) —
  un-grandfathers 51 agents. 13 off-enum values (magenta/teal/indigo/gold/amber) remapped to
  nearest enum in this PR.
- **`skills` is now official** — preloads full skill content into the agent at startup.
  Un-grandfathers 3 agents (db-migration, embedded-device, swift-backend), whose preloads now
  actually work.
- **New fields we don't use yet** (accepted by the validator, adoption optional):
  `permissionMode`, `maxTurns`, `mcpServers`, `memory` (persistent cross-session learning),
  `background` (subagents are background-by-default since v2.1.198), `isolation: worktree`
  (official fix for the shared-working-tree incident in CLAUDE.md Rule 2), `initialPrompt`.
- **`model: fable`** is a valid alias now (Fable 5, v2.1.170). All 59 agents use
  sonnet/opus/haiku; re-tiering is a roster decision, not a spec fix.
- **Skills-only fields on agents now HARD-fail** in our validator (`allowed-tools`,
  `when_to_use`, `disable-model-invocation`, `context`, `agent`, `paths`, `user-invocable`) —
  they're silently ignored, which is worse than unknown keys: the author believes a
  restriction is active when it is not.

## Behavior changes worth knowing (no repo action needed)

- **Background by default** (v2.1.198): subagents run in background unless the result is
  needed immediately; permission prompts surface in the main session with attribution (v2.1.186).
- **Nesting to 5 levels** (v2.1.172); implicit agent teams (v2.1.178).
- Subagents inherit session extended-thinking config (v2.1.198); API errors are reported
  instead of failing silently (v2.1.199).
- Skill stacking `/a /b args` up to 5 skills (v2.1.199); `/reload-skills` (v2.1.152).

## Follow-ups (filed as opportunities, not debt)

1. **"use proactively" phrasing** — adopt selectively on agents that *should* auto-fire
   (e.g. infra-reviewer post-Terraform-change), not as a blanket sweep.
2. **`memory:` field** — candidates: hiring-manager (roster history), sales-rep (deal
   patterns across sessions — could complement `/sales-pipeline`'s `~/.inc` files).
3. **`isolation: worktree`** — consider defaulting for review/inspection fan-outs; it's the
   official mechanism for the Rule 2 shared-tree caution.
4. **Model re-tiering with `fable`** — roster decision; revisit when a role visibly needs it.
