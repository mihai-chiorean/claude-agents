# MIT-410: Claude Code Agent and Skill Authoring Specification

> **2026-06-19 — partially superseded.** The AGENT frontmatter field list below is stale: the June-2026 spec renamed agent tool restriction to `tools`/`disallowedTools`, legalized `color` and `skills`, and added permissionMode/maxTurns/mcpServers/memory/background/isolation/initialPrompt. See `research/agent-spec-currency-2026-06.md`. The SKILL field list remains current.


**Research Date**: May 27, 2026  
**Status**: Ground-truth extraction from Anthropic Claude Code documentation  
**Scope**: Agent file format, skill format, sub-agent invocation, routing, and recent changes

---

## 1. Full Agent/Sub-agent File Spec

### Frontmatter (YAML)

**Official spec location**: [https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) → "Write subagent files" → "Supported frontmatter fields"

**Supported frontmatter fields** (exact quote from docs):

```yaml
---
name: (optional) Display name
description: What this agent does and when to use it
model: sonnet | opus | haiku | (inherit to keep active model)
effort: low | medium | high | xhigh | max
allowed-tools: Tool1 Tool2 (space/comma-separated or YAML list)
disallowed-tools: (space/comma-separated or YAML list)
user-invocable: true | false
disable-model-invocation: true | false
context: fork (to run in forked subagent context)
agent: Explore | Plan | general-purpose | (custom agent name)
hooks: (subagent-scoped hooks)
paths: (glob patterns for path-specific activation)
---
```

**Notes**:
- **No `tools` field exists in agents** — agents don't declare a tools list. Instead, they inherit the parent session's tool availability and override with `allowed-tools` / `disallowed-tools`.
- **No `color` field** — color is inferred from the agent's role, not declared.
- **No `scope` field** — agents don't have "scope" like skills do.
- **Model field behavior**: "Model to use when this skill is active. The override applies for the rest of the current turn and is not saved to settings; the session model resumes on your next prompt."

### Body Structure

**Official guidance**: [https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) → "Example subagents"

**Body is free-form markdown** — the agent's system prompt/instructions. No required sections beyond frontmatter.

**Examples from official docs**:

**Code Reviewer Agent**:
```markdown
---
name: Code Reviewer
description: Reviews code for best practices, security issues, and improvements
---

You are an expert code reviewer. Review the provided code for:
- Security vulnerabilities
- Performance issues
- Code style and conventions
- Test coverage
- Documentation quality
```

**Debugger Agent**:
```markdown
---
name: Debugger
description: Debugs issues and finds root causes
model: opus
---

You are an expert debugger. When given an error or unexpected behavior:
1. Understand the symptoms
2. Form hypotheses
3. Test each hypothesis systematically
4. Explain the root cause
5. Suggest fixes
```

**Length conventions**: Docs mention agents can be "concise" but don't specify max length. In practice, they load entirely (unlike skills, which load on demand). Similar to CLAUDE.md philosophy: "state what to do rather than narrating how or why."

---

## 2. How Claude Code Loads and Invokes Sub-agents

**Official spec**: [https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) → "Work with subagents" section

### Context Passed to Sub-agent

**What loads at startup** (exact quote):

> "Explore and Plan agents [skip CLAUDE.md and git status](https://code.claude.com/docs/en/sub-agents.md#what-loads-at-startup) to keep their context small. Subagents receive: (1) their own system prompt, (2) preloaded skills (if any), (3) CLAUDE.md from the parent project (except Explore/Plan agents)."

**Sub-agent sees**:
- The subagent's own frontmatter system prompt
- The user's delegation prompt (the message Claude forwarded to the subagent)
- **NOT** the parent conversation history
- **NOT** the parent's current file context (unless explicitly passed via the delegation message)
- Preloaded skills (if the subagent has `skills` field defined)
- CLAUDE.md (unless agent is Explore or Plan)
- Git status (unless agent is Explore or Plan)

### Model Override

**`model` field**: Pins a specific model for that subagent. From docs:

> "Set to a model name to pin this subagent to that model. The override applies for the rest of the current turn and is not saved to settings; the session model resumes on your next prompt."

**This is per-invocation**, not persisted.

### Tools Field

**Spec is silent on agents having a `tools` field.** There is **no `tools` frontmatter field for agents**.

Instead:
- `allowed-tools` (YAML list or space/comma-separated string): "Tools Claude can use without asking permission when this subagent is active."
- `disallowed-tools` (same format): "Tools removed from Claude's available pool while this subagent is active."

### Automatic Selection vs. Explicit Invocation

**Official guidance** ([https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) → "Understand automatic delegation"):

> "Claude uses each subagent's description to decide when to delegate tasks. When you create a subagent, write a clear description so Claude knows when to use it."

**Routing is description-based**, not name-based. The router LLM reads the agent's description and fires it when it matches the current task context.

---

## 3. Anthropic's Official Example Agents

**Source**: [https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) → "Example subagents" section

### Code Reviewer (verbatim)

```markdown
---
name: Code Reviewer
description: Reviews code for best practices, security issues, and improvements
---

You are an expert code reviewer. Review the provided code for:
- Security vulnerabilities
- Performance issues
- Code style and conventions
- Test coverage
- Documentation quality

Provide specific, actionable feedback. Flag critical issues first.
```

### Debugger (verbatim)

```markdown
---
name: Debugger
description: Debugs issues and finds root causes
model: opus
---

You are an expert debugger. When given an error or unexpected behavior:
1. Understand the symptoms
2. Form hypotheses
3. Test each hypothesis systematically
4. Explain the root cause
5. Suggest fixes

Be methodical. Avoid guessing.
```

### Data Scientist (verbatim)

```markdown
---
name: Data Scientist
description: Analyzes data and creates visualizations
---

You are an expert data scientist. When given a dataset:
1. Explore the structure and summary statistics
2. Identify patterns and anomalies
3. Perform exploratory analysis
4. Create clear visualizations
5. Summarize findings

Use code to perform analysis when needed.
```

**Canonical shape observations**:
- Description is 1-2 sentences, clear trigger phrases ("Reviews code", "Debugs issues", "Analyzes data")
- Body is 50-150 words: numbered list of responsibilities + key constraint
- **No examples (<example> blocks) in agent body** — those live in skills
- **Model override only when needed** (Debugger uses `opus` for harder problems)
- **No `tools`, `allowed-tools`, or `disallowed-tools`** in the shown examples

---

## 4. Skill Spec

**Official spec**: [https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md)

### SKILL.md Structure

**Required**: `.SKILL.md` file with YAML frontmatter + markdown body.

**Optional supporting files**:
```
my-skill/
├── SKILL.md (required)
├── template.md (optional, for Claude to fill in)
├── examples/ (optional, reference outputs)
└── scripts/ (optional, executables Claude can run)
```

### Frontmatter Fields (Skills)

**Complete reference** from [https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md) → "Frontmatter reference":

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | No | String | Display name. Defaults to directory name. Does NOT set command name (only applies to plugin root SKILL.md). |
| `description` | Recommended | String | "What the skill does and when to use it." **Capped at 1,536 chars** (combined with `when_to_use`). Used for routing. |
| `when_to_use` | No | String | Additional trigger context. Appended to `description`, counts toward 1,536-char cap. |
| `argument-hint` | No | String | Display text during autocomplete, e.g. `[issue-number]` or `[filename] [format]`. |
| `arguments` | No | List or String | Named positional arguments for `$name` substitution. Space-separated string or YAML list. |
| `disable-model-invocation` | No | Boolean | `true` to prevent Claude from auto-loading. Default: `false`. |
| `user-invocable` | No | Boolean | `false` to hide from `/` menu. Default: `true`. |
| `allowed-tools` | No | List or String | Tools Claude can use without permission when skill is active. Space/comma-separated or YAML list. |
| `disallowed-tools` | No | List or String | Tools removed from pool while skill is active. |
| `model` | No | String | Model override for this skill. Accepts same values as `/model` or `inherit`. |
| `effort` | No | String | Effort level override: `low`, `medium`, `high`, `xhigh`, `max`. |
| `context` | No | String | Set to `fork` to run in a forked subagent context. |
| `agent` | No | String | Which subagent to use when `context: fork`. Defaults to `general-purpose`. |
| `hooks` | No | Object | Skill-scoped hooks configuration. |
| `paths` | No | List or String | Glob patterns for path-specific activation. |
| `shell` | No | String | `bash` (default) or `powershell`. |

**Key differences from agents**:
- Skills have `description` + optional `when_to_use` (agents just have `description`)
- Skills have `arguments` (agents do not)
- Skills have `context: fork` and `agent` (agents define their own system prompt)
- Skills support `allowed-tools` and `disallowed-tools` (agents do too)
- **Crucially**: Skills do NOT have a `tools` field. Skills and agents both omit it.

### Body

**Free-form markdown** with optional dynamic context injection:

```markdown
---
description: Summarizes uncommitted changes
---

## Current changes

!`git diff HEAD`

## Instructions

Summarize the changes above...
```

**Dynamic context**: `` !`command` `` syntax runs shell commands before Claude sees the skill. Output replaces the placeholder.

### Skill vs. Agent Decision Rubric

**Official guidance** ([https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md) → "Configure skills" → "Types of skill content"):

> "Skill files can contain any instructions, but thinking about how you want to invoke them helps guide what to include:
> - **Reference content** adds knowledge Claude applies to your current work... This content runs inline so Claude can use it alongside your conversation context.
> - **Task content** gives Claude step-by-step instructions for a specific action, like deployments, commits, or code generation."

**Subtly different from agents**:
- **Skills** are reference material or task instructions that load into the current conversation
- **Agents** are isolated specialists with their own system prompt, tools, and context window
- Use **skills** when you want to augment the current conversation with knowledge or procedures
- Use **agents** when you want to delegate a side task to an isolated context

---

## 5. Plugin Format Implications

**Official spec**: [https://code.claude.com/docs/en/plugins.md](https://code.claude.com/docs/en/plugins.md)

### Plugin Manifest (plugin.json)

**Schema** (exact from docs):

```json
{
  "name": "unique-identifier",
  "description": "Human-readable description",
  "version": "1.0.0",
  "author": {
    "name": "Your Name"
  }
}
```

### Plugin Directory Structure

**Required**: `.claude-plugin/plugin.json`  
**Optional directories at plugin root** (NOT inside `.claude-plugin/`):

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json (required)
├── skills/
│   └── <skill-name>/SKILL.md
├── agents/
│   └── <agent-name>.md
├── commands/
│   └── <command-name>.md
├── hooks/
│   └── hooks.json
├── .mcp.json
├── .lsp.json
└── bin/
```

### Agent/Skill Authoring in Plugins

**No changes to the spec itself** — agents and skills written in plugins use the same YAML frontmatter and body format. The only difference is **namespacing**: skills become `/plugin-name:skill-name`, not `/skill-name`.

---

## 6. Recent Changes (2026)

**Changelog source**: [https://code.claude.com/docs/en/changelog.md](https://code.claude.com/docs/en/changelog.md)

### v2.1.152 (May 27, 2026)

- **`/reload-skills` command**: Re-scan skill directories without restarting
- **`SessionStart` hooks**: Can now set `sessionTitle` and return `reloadSkills: true`
- **`MessageDisplay` hook event**: New hook type to transform or hide assistant messages

### Earlier in 2026

- **v2.1.111**: Opus 4.7 with `xhigh` effort available
- **v2.1.139**: Agent view with `claude agents` command for unified session dashboard

### No breaking changes to agent/skill format spec** in 2026 documented so far. The YAML frontmatter and body structure have remained stable.

---

## 7. Description Writing Guidance

**Official guidance** ([https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md) → "Frontmatter reference"):

> "`description`: What the skill does and when to use it. Claude uses this to decide when to apply the skill. If omitted, uses the first paragraph of markdown content. Put the key use case first: the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage."

### Style Recommendations

**Exact text from official docs**:

> "Write a clear description so Claude knows when to use it... When you create a subagent, write a clear description so Claude knows when to use it."

**For agents specifically** ([https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md)):

> "Claude uses each subagent's description to decide when to delegate tasks."

### Why 1,536 chars?

**Architectural reason**: Descriptions load into context proactively so Claude knows what agents/skills are available. The cap ensures skill metadata doesn't consume context unnecessarily. From docs:

> "All skill names are always included, but if you have many skills, descriptions are shortened to fit the character budget, which can strip the keywords Claude needs to match your request."

### Router Consumption

Descriptions are read by an internal router LLM that decides whether to invoke the skill/agent. They are **also preloaded** into the agent's context as part of the skill or agent listing, so the model can reference them.

---

## 8. What Good vs. Bad Looks Like

### Anti-patterns (from official docs)

**Skills that are too vague** ([https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md) → "Troubleshooting"):

> "If Claude doesn't use your skill when expected: Check the description includes keywords users would naturally say."

**Example of bad description**:
```yaml
description: Helper for stuff
```

**Example of good description** (from official examples):
```yaml
description: Summarizes uncommitted changes and flags anything risky. Use when the user asks what changed, wants a commit message, or asks to review their diff.
```

**Skills with `disable-model-invocation: true` but no clear task** ([https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md) → "Control who invokes a skill"):

> "`disable-model-invocation: true`: Only you can invoke the skill. Use this for workflows with side effects or that you want to control timing, like `/commit`, `/deploy`, or `/send-slack-message`. You don't want Claude deciding to deploy because your code looks ready."

**Subagents without actionable bodies**:

From docs: "Subagents with `context: fork` [must have explicit instructions](https://code.claude.com/docs/en/skills.md#run-skills-in-a-subagent). If your skill contains guidelines like 'use these API conventions' without a task, the subagent receives the guidelines but no actionable prompt, and returns without meaningful output."

### What Anthropic explicitly says to avoid

- **Vague descriptions** that don't include trigger keywords
- **Side-effect operations** (`/deploy`, `/send-slack`) without `disable-model-invocation: true`
- **Overly long frontmatter descriptions** (>1,536 chars)
- **Missing the first-turn task** in subagent bodies

---

## What I Couldn't Find

1. **Agent tools field precedent**: Docs are silent on whether agents ever had a `tools` field. They don't now, and the spec makes no reference to it.

2. **Max agent body length**: Unlike skills (which have token cost guidance), there's no documented max length for agent bodies. Likely they can be as large as needed since they're invoked infrequently, but empirically untested here.

3. **Example blocks in agents**: Official examples don't include `<example>` blocks in agent bodies. Skills can reference supporting files including `examples/`, but whether agents can reference examples is not documented.

4. **Sub-agent spawning from tasks**: When Claude delegates to a subagent via the Agent tool (internally), the exact message format passed to the subagent is not fully documented. We know the skill/prompt content is passed, but the wrapping is opaque.

5. **Routing confidence threshold**: The router LLM that decides whether a skill matches context has no documented confidence threshold or rejection behavior documented.

6. **Context window for agents**: Subagents get their own context window, but the size is not explicitly stated (likely same as main session, but untested).

7. **`disable-model-invocation: true` on agents**: Skills support this, but the docs don't clarify if agents can use it (probably not applicable since agents don't auto-fire the same way skills do).

8. **Subagent task timeout**: If a subagent runs longer than some threshold, docs don't specify what happens.

---

**Report prepared**: May 27, 2026  
**Source docs used**:
- [https://code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md)
- [https://code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md)
- [https://code.claude.com/docs/en/plugins.md](https://code.claude.com/docs/en/plugins.md)
- [https://code.claude.com/docs/en/changelog.md](https://code.claude.com/docs/en/changelog.md)
