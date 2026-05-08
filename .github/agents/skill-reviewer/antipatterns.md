# The five SKILL.md antipatterns

Source: Lax Meiyappan, "What you're actually writing when you write a SKILL.md," *INTERNALS.md* #2 (Apr 2026), drawing on Anthropic's Agent Skills runtime documentation.

A skill is a small program with three execution stages. Every failure mode below comes from violating that runtime contract by treating skills like prompts.

---

## #1 — Frontmatter on reference files

**The mistake.** Adding YAML frontmatter (`---\nname: ...\ndescription: ...\n---`) to a reference markdown file because `SKILL.md` has it and the reference "feels important enough."

**Why it breaks.** Frontmatter is what gets loaded into the system prompt at startup. *Every* file with frontmatter contributes its `name` and `description` to the always-loaded set — the pinboard. Adding it to a reference promotes a sub-page to skill-level visibility. The agent will now sometimes trigger the reference *directly*, without the parent SKILL.md body that gives it meaning. The output is subtly wrong and the cause is invisible because the reference file looks fine in isolation.

**The fix.** Delete the frontmatter from references. They are chapters, not skills.

**How to detect.** Any `.md` file under `skills/<name>/` that is *not* `SKILL.md` and starts with `---` on line 1.

---

## #2 — One monolithic SKILL.md

**The mistake.** Putting workflow, module map, contracts, code patterns, and gotchas all in one ~1,200-line `SKILL.md`. "Cleaner. One file. Easy to read."

**Why it breaks.** Every time the skill triggers, the agent loads the entire file even when the task only needs two of its four sections. The article's measured number: a skill that should cost 7% of the context window costs 20%. That penalty compounds — install three monolithic skills and longer sessions hit compaction cliffs sooner.

**The fix.** Split into a short spine (~150–250 lines) that points to references. Move the module map, the contracts, and the deep gotchas into `<topic>.md` files in the same folder. The spine names them and explains *when* to read each.

**How to detect.** SKILL.md > 500 lines (Anthropic's recommended ceiling) is a Blocker. SKILL.md 300–500 lines is a yellow warning — review whether sections are independently accessed.

---

## #3 — Hardcoded workspace paths

**The mistake.** Writing instructions like *"navigate to `modules/web` and run the build"* — paths that work in your repo but not your teammate's.

**Why it breaks.** This failure mode does not appear until you share. On your machine it always works. The moment another engineer runs the skill, every implicit path assumption surfaces as a silent bug — the build runs in the wrong directory and produces output in the wrong place. No error.

**The fix.** Write instructions that ask the agent to *discover* the right path rather than declare it. *"Search for the build configuration. Identify the module by its `package.json`. Read the workspace structure before assuming."* The skill becomes more abstract and more portable.

**How to detect.** Absolute paths (`/Users/...`, `/home/...`, `C:\...`), single hardcoded relative module paths in command examples, repo-specific names like `modules/web` without a "find this in your repo" preamble.

---

## #4 — Missing Gotchas

**The mistake.** Trusting that the agent's defaults will handle your environment.

**Why it breaks.** The agent has reasonable priors. Your environment is not average. Turborepo wants the build run from the repo root or the dependency graph misreads. The agent's default — *"I'm in the `web` module, I'll run from here"* — is correct in 90% of repos. It is silently wrong in yours. No amount of "explain the why" prevents this; the wrongness is environmental, not conceptual.

**The fix.** A single line in a Gotchas section: *"Always run `turbo build` from the repository root, never from inside a module."* Mature skills treat the Gotchas section as the most important section to maintain over time. Every time the agent does the wrong thing in production, a Gotcha line is the diff.

**How to detect.** Operational skills (deployment, connection, setup, runtime) without a `## Gotchas`, `## Pitfalls`, `## Common mistakes`, or equivalent section *anywhere in the skill* (SKILL.md or any reference).

---

## #5 — No evals

**The mistake.** Tuning a skill on one model and calling it done. *"It worked when I tested it"* is not evidence — it is the absence of measurement.

**Why it breaks.** A more capable model interprets your instructions instead of following them. A writing skill tuned on Sonnet (which read "short sentences" with judgment) produced choppy bullet-prose on Opus (which read "short sentences" as a hard constraint). The capability went up; the fit went down. Without evals you cannot tell.

**The fix.** A small Golden Set per skill — three or four realistic prompts, with paired runs (with skill / without skill) and a few scriptable assertions (output length, presence of required structure, absence of forbidden patterns). Re-run on every model bump, every skill edit. Anthropic's `skill-creator` builds this in via its `eval-viewer`.

**How to detect.** No `evals/`, `tests/`, `golden-set/`, or `eval.{md,json,yaml}` artifact alongside the skill. This is a soft signal — many useful skills ship without evals — so flag as Improvement, not Blocker, unless the skill encodes voice, formatting, or other compliance-sensitive behavior.

---

## Quick reference: severity mapping

| Antipattern | Default severity | When to escalate |
|---|---|---|
| #1 frontmatter on references | 🔴 Blocker | always |
| #2 monolithic SKILL.md | 🔴 Blocker if > 500 lines, 🟡 Improvement if 300–500 | always |
| #3 hardcoded paths | 🟡 Improvement | 🔴 if absolute paths in shell commands |
| #4 missing Gotchas | 🟡 Improvement | 🔴 only if the skill has caused a known production issue |
| #5 no evals | 🟡 Improvement | 🔴 only for voice/compliance skills |
