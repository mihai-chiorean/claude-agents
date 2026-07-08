# inc — operating rules

This file is auto-loaded by Claude Code at session start. It is **deliberately minimal**: every rule has earned its place by closing a failure mode observed in this repo. Other discipline (codex-review-before-merge, coverage gates, ETHOS philosophy) lives elsewhere and gets promoted into this file only if its absence costs real time.

The current scope is informed by the gstack-borrow review — see `research/gstack-borrow-2026-05-11.md`.

---

## Rule 1 — Session bootstrap

On session start, **run or offer `/sitrep`** before doing other work. `/sitrep` reads `STATUS.md` + Linear + open PRs and surfaces "where you are, what's next, what's blocked on you." If the user's first message is an explicit task that bypasses bootstrap, do the task — but still surface a one-line orientation ("on branch X for MIT-Y; next was Z") from `STATUS.md` if it's present.

When work concludes, update `STATUS.md` (active branch, active PR, next command, last_verified_state). The schema lives at `skills/sitrep/docs/status-schema.md`.

## Rule 2 — Specialist routing

**Delegation to the roster is the default, not something the user has to ask for.** When a request matches a specialist agent's domain, route to it via the Agent tool without being told to — read "do X" as "get X done by whoever owns X," not "do X yourself." Do not wait for the user to say "delegate this," "use an agent," or "use the roster"; assume that is the standing intent for any domain work. Do not redo work specialists exist to handle. When in doubt, route. Run independent pieces of work as parallel agents in a single message rather than serially. The roster is the `agent.manifest.yaml` at the repo root, surfaced per-project by the `/staff` skill.

The bar for doing it yourself instead of routing: the task is trivial, falls outside every specialist's domain, or *is* the orchestration itself (sequencing agents, reconciling their output, landing merges, talking to the user). Everything with a clear domain owner goes to that owner by default.

One caution learned in practice: agents you spawn share this working tree. An agent that runs `git checkout`/`git worktree` in the main checkout can leave it on a detached HEAD and silently revert your uncommitted edits. When you fan out review/inspection agents, tell them to read diffs (`gh pr diff`) or spawn them with `isolation: worktree` (the official mechanism — the agent gets its own temporary worktree, auto-cleaned if unchanged). Caveat: an isolated worktree branches from the *default branch*, not your session's HEAD, so don't use it for agents that must see your uncommitted changes — those read diffs instead. Never switch branches in the shared checkout.

Specialists own depth. Skills own procedure. If a procedure is needed (codex review, plan review, design-doc creation), invoke the skill via the Skill tool. If a domain is needed (Swift backend, GPU, security audit), spawn the agent.

## Rule 3 — Linear-as-inbox

Linear is the queue and the history. The **inbox** is anything assigned to the user, any open PR awaiting their review, and any design doc flagged for review. `/sitrep` surfaces all three. Agents that produce review-worthy artifacts should create or update Linear items assigned back to the user (with a link), not leave them in chat or as wandering files.

When the user asks "what's on my plate" or "what needs my attention," go to Linear (via `sitrep-linear inbox`) and open PRs (via `gh pr list --search 'review-requested:@me'`), not to a chat-history reconstruction.

## Rule 4 — Break down non-trivial work before doing it

When the user **plans or queues new work** that is more than a one-line fix — phrases like "let's build", "we should ship", "I want to start on", "how do we break this down" — **invoke `/work-breakdown`** before writing code. The skill classifies size (S/M/L/XL), creates the right Linear artifacts (issue / project + issues / initiative + projects), recommends specialist agents to bring in, and names the required planning gates.

Do **not** invoke when the user is asking for immediate execution of an already-scoped change ("fix this", "implement X now", "just do it"). The trigger is *planning intent*, not size alone.

If unsure whether to fire, ask one clarifying question: "is this one PR or should we break it down?"

## Rule 5 — Surface conflicts, don't average them

When two parts of the system disagree — two existing code patterns, two specialist agents (PM vs tech-lead), codex feedback vs your own analysis, a doc vs the code — **pick one explicitly and say why**. Do not blend them. Blended behavior that tries to satisfy both keeps the conflict hidden and grows incoherent over time.

The right move when two patterns contradict:
1. State both positions in one sentence each.
2. Pick one (usually: more recent, more tested, or matches the explicit user preference if there is one).
3. Flag the other as a follow-up — a Linear issue, a `decisions/` entry, or at minimum a line in the next commit message.

When **specialists** disagree, distinguish material from cosmetic:

- **Material disagreement** — different recommendations on scope, architecture, risk, schedule, or user-visible behavior. Surface to the user; do not silently pick one. User Sovereignty applies.
- **Cosmetic / stylistic disagreement** — preference about wording, ordering, minor structure. Pick one, log the rationale in the commit or PR description, move on. Do not escalate.

This rule is anticipatory more than retrospective — we have not yet hit a multi-specialist deadlock in this repo, but the setup (`/work-breakdown` recommending PM + tech-lead + codex on L-sized work) makes it a question of when, not if.

## Rule 6 — Fail loud

Default to surfacing uncertainty, not hiding it. Specifically:

- **"Completed"** is wrong if anything was silently skipped, deferred, or stubbed. Name what was skipped and why.
- **"Tests pass"** is wrong if any tests were skipped, xfail'd, or removed. Report the skip count.
- **"Works"** is wrong if you did not verify the edge case the user asked about. Name the verified path and the unverified one.
- **"Migration ran"** is wrong if records hit constraint violations and were silently dropped. Always report a count.

When you cannot verify something worked, **say so explicitly in the same sentence as the claim of success**. Burying caveats in a long paragraph is functionally the same as silent failure — the user reads "done" and moves on.

This rule has teeth because codex review caught silent-skip behavior twice during Week 1 of the gstack-borrow initiative. Promoting it from "we happen to catch this" to "expected default."

## Rule 7 — Investigation tickets ship markdown reports, not PRs

When picking up a Linear ticket whose **primary ask is to answer a question or produce a recommendation** — research, investigation, spike, audit, diagnose, triage, root-cause, assess, inventory, map, survey, exploration, "figure out X," "compare options for," "evaluate whether to" — the deliverable is **a markdown report attached to the Linear issue**, not a code PR. Use `linear issue attach MIT-NNN <path-to-md>`.

Override only when the user explicitly asks for code changes ("implement what you found", "turn this into a PR"). If the ticket's shape is ambiguous, ask one clarifying question before branching: "report-shaped or PR-shaped?"

This prevents the reflexive `ticket → branch → PR` pattern that mismatches investigation work — where the artifact IS the deliverable, and a PR is overhead. The longer "how" (classification, report shape, file path convention) lives in `docs/getting-started/workflow.md` §6 "Ticket shape: implementation vs investigation."

## Rule 8 — Run the validators before pushing agent or manifest changes

When you've touched an agent .md file, the manifest, or anything under `engineering/` / `product/` / `marketing/` / `testing/` / `writing/` / `design/` / `project-management/` / `studio-operations/` / `bonus/`, run the two local checks before pushing:

```bash
python3 scripts/validate-agents.py    # strict YAML + spec checks per MIT-392
python3 scripts/generate-manifest.py  # regen + commit if anything changed
```

CI runs the same checks via `.github/workflows/validate.yml` and blocks merge on hard-fail. Running locally first surfaces problems before the round-trip through PR.

This rule has teeth because MIT-392 found that 52 of 57 agent files had silently been failing strict YAML, with Claude Code's loader truncating descriptions at the first parse failure. Without the validator, the next person to add a multi-line `<example>` block to a description would re-introduce the same bug invisibly.

---

## Defer (not in this CLAUDE.md, yet)

The following are explicitly NOT enforced by this CLAUDE.md. Promote them only if their absence is observed to cost time:

- Codex review × 3 rounds per PR (currently done by convention; not a CLAUDE.md rule yet).
- 80% test coverage gate (project-specific; lives in `Makefile` for repos that need it).
- Boil-the-lake stance (procedural completeness vs feature scope — see handoff for the nuanced version).
- ETHOS.md cultural principles.

These may be promoted in a later week of the gstack-borrow initiative if they prove load-bearing.

## Pointers

- **Session-state contract:** `STATUS.md` at this repo's root. Schema at `skills/sitrep/docs/status-schema.md`.
- **Agent roster:** `agent.manifest.yaml` (top-level). Per-project staffing: `/staff` skill.
- **Active initiative:** gstack-borrow ([Linear](https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96)). Handoff at `research/gstack-borrow-2026-05-11.md`.
