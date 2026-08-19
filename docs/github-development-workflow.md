# Reusable GitHub project operating system

This document defines a project method that can be copied into a new software,
engineering, research, documentation, or creative project. It is designed for
human/AI collaboration where work must remain reviewable across chats,
machines, tools, and time.

The central idea is simple:

> The repository stores durable knowledge, issues store work contracts, pull
> requests store reviewable changes, and project statuses store evidence gates.
> Chat is an execution interface, not the sole source of truth.

## 1. Information architecture

Use each artifact for one job:

| Artifact | Purpose |
| --- | --- |
| `README.md` | Current purpose, status, entry points, and how to begin |
| `AGENTS.md` | Persistent operating instructions for AI agents |
| `docs/architecture.md` | System boundaries and durable decisions |
| `docs/roadmap.md` | Ordered outcomes and decision gates |
| GitHub parent issue | Initiative/epic, dependencies, and stage order |
| GitHub child issue | One executable work contract |
| Branch | Isolated implementation of one work contract |
| Pull request | Review, evidence, discussion, and merge gate |
| GitHub Project | Portfolio view and handoff state |
| Issue comments | Timestamped evidence and handoffs |
| Final chat response | Immediate, copy-ready handoff for the operator |

Do not duplicate the same changing truth in five places. Stable rules belong in
the repository. Current scope and acceptance criteria belong in the issue.
Evidence belongs in the PR/issue. The Project summarizes state.

## 2. Project startup

### 2.0 Verify GitHub access

Before relying on CLI automation, check:

```bash
git remote -v
gh auth status
```

If the GitHub CLI token is missing or invalid, reauthenticate interactively:

```bash
gh auth login -h github.com
```

Do not place GitHub tokens in repository files, issue bodies, prompts, or shell
history. A working Git remote does not prove that `gh` API authentication is
valid; verify both separately.

### 2.1 Define the project contract

Before implementation, record:

- desired outcome and why it matters;
- users/stakeholders;
- explicit non-goals;
- constraints, risks, confidential inputs, and safety boundaries;
- evidence that will count as success;
- decisions that are reversible versus expensive to reverse;
- known external dependencies and validation environments.

Put the short version in `README.md`, AI operating rules in `AGENTS.md`, and
long-lived design decisions in `docs/`.

### 2.2 Build an outcome roadmap

Create one parent issue for the initiative and child issues for the smallest
independently reviewable stages. Order by dependency and learning value, not by
the apparent order in which someone first imagined the final product.

A good early stage reduces a major uncertainty. It does not merely create
scaffolding.

### 2.3 Configure a GitHub Project

Recommended fields:

| Field | Example values |
| --- | --- |
| Status | Backlog, Ready, In progress, In review, Done |
| Handoff | None, Ready for implementation, Ready for validation, Blocked |
| Priority | P0, P1, P2, P3 |
| Type | Research, Feature, Documentation, Validation, Decision |
| Area | Project-specific subsystem/domain |
| Validation | Not required, Pending, Passed, Failed |

Use as few fields as possible while preserving decisions people actually make.

## 3. Evidence-gated statuses

Statuses must describe what evidence exists, not a subjective percentage:

| State | Entry condition | Exit evidence |
| --- | --- | --- |
| `Backlog` | Valuable but not ready or dependency open | Dependency resolved and issue contract reviewed |
| `Ready` | Scope, owner/agent, inputs, and acceptance criteria exist | Work branch or active execution begins |
| `In progress` | Implementation/research is active | Deliverable and local checks are ready for review |
| `In review` | PR/deliverable is reviewable | Review and required validation pass |
| `Ready for validation` | Exact artifact/revision handed to another environment/person | Validation evidence returned |
| `Blocked` | Specific external decision/input prevents progress | Blocking condition changes |
| `Done` | All required evidence gates pass | Terminal state |

Do not mark work `Done` because a chat ended, code compiled, a PR merged, or an
AI claimed confidence. Define the required evidence explicitly.

## 4. Work-item issue contract

Every executable child issue should contain:

### Context

- parent initiative;
- predecessor/dependency links;
- problem or opportunity;
- current evidence and relevant decisions.

### Objective

- one concrete outcome;
- user/stakeholder value;
- why this is the next useful slice.

### Scope

- required deliverables;
- explicit non-goals;
- allowed and prohibited mutations/actions;
- input/output and confidentiality boundary.

### Acceptance criteria

- observable pass/fail statements;
- required tests, reviews, measurements, or human decisions;
- required documentation and cleanup;
- environment-specific gates.

### Handoff

- responsible next role/environment;
- exact branch, commit, document version, dataset, or artifact;
- copy-ready next prompt/instructions;
- unresolved assumptions.

If the issue cannot state these clearly, it is still discovery work. Create a
bounded research/decision issue rather than pretending implementation is ready.

## 5. Branch and pull-request contract

Use one branch and normally one PR per child issue:

```text
codex/<issue-number>-<short-purpose>
```

Keep the PR draft until its implementation gate is complete. The PR should
state:

- issue closed or advanced;
- exact scope and non-goals;
- safety/data assumptions;
- changed artifacts;
- checks performed and their results;
- evidence still missing;
- exact artifact/revision for external validation;
- rollback or recovery path where relevant.

Do not force-push an exact commit already handed to validation. If it changes,
post the replacement commit and explicitly invalidate the former target.

A merged PR proves integration into the repository. It does not automatically
prove domain correctness, licensed-runtime behavior, field validation, user
acceptance, or deployment success.

## 6. Multiple environments and roles

Many projects have evidence that can only be produced elsewhere:

- development machine versus licensed test machine;
- synthetic data versus confidential production data;
- lab bench versus design workstation;
- draft author versus legal/domain reviewer;
- simulation versus physical experiment;
- offline analysis versus deployed system.

Define each environment's authority:

| Environment/role | May change | May validate | Must not claim |
| --- | --- | --- | --- |
| Implementation | Source/artifacts and local tests | Internal consistency and fake/synthetic cases | External-runtime or field success |
| Validation | Normally configuration/test inputs only | Real environment behavior | Unreviewed implementation changes |
| Reviewer/approver | Acceptance decision | Fit to contract and evidence quality | Results not present in evidence |

Keep synthetic, inferred, and real-world results explicitly separated.

## 7. Handoff protocol

Every handoff must be delivered twice:

1. durable record in the GitHub issue/PR;
2. short, fully copyable instructions in the final chat response.

This avoids two failure modes: chat-only knowledge disappears, while
issue-only instructions are easy for the operator to miss.

### Implementation-to-validation template

```markdown
## Ready for validation

- Issue: #<number>
- Branch: `<branch>`
- Exact artifact/commit: `<identifier>`
- Implemented scope: `<summary>`
- Checks already passed: `<commands/reviews/results>`
- Not yet validated: `<assumptions>`
- Validation inputs/environment: `<safe details>`
- Allowed actions: `<bounded actions>`
- Prohibited actions: `<non-goals>`
- Expected evidence: `<fields, measurements, cleanup>`
- Next prompt: `<copy-ready instruction>`
```

### Validation-to-implementation template

```markdown
## Validation evidence

- Issue: #<number>
- Exact artifact/commit tested: `<identifier>`
- Environment/version: `<facts>`
- Procedure: `<ordered steps>`
- Observed result: `<safe evidence>`
- Cleanup/recovery: `<result>`
- Outcome: `passed | failed | blocked`
- Discrepancy/reproduction: `<details>`
- Source/artifact changed during validation: `no` (normal path)
- Next prompt: `<copy-ready instruction>`
```

## 8. AI-agent operating rules

Put a concise version of these rules in `AGENTS.md`:

1. Read the named issue and repository instructions before acting.
2. Verify repository/machine/environment role.
3. Inspect Git status and preserve unrelated work.
4. Work only inside the issue scope and explicit authority boundary.
5. Verify unstable facts against primary sources.
6. Distinguish read-only diagnostics from mutations.
7. Add proportionate tests/evidence and record what remains unknown.
8. Never invent external validation or domain results.
9. Avoid force-pushes and destructive cleanup.
10. Update the durable issue and repeat the handoff in the final response.

### Minimal new-task starter

After the repository and issue contract are mature, a new AI chat should need
only:

```text
Work on GitHub issue #<number> in this repository. Read AGENTS.md, the issue
body, dependencies, and latest handoff comments first. Verify the current
environment/role, preserve unrelated changes, execute only the issue scope,
record evidence in the issue, and include the copy-ready next handoff in the
final response.
```

If this prompt is insufficient, improve the repository/issue contract instead
of repeatedly writing longer disposable chat prompts.

## 9. Automation boundary

Automation may:

- apply labels and add issues to a Project;
- validate that required issue fields are present;
- link PRs/issues and update status from objective repository events;
- remind owners about missing evidence;
- run deterministic tests and formatting checks.

Automation must not:

- infer domain or licensed validation from CI;
- mark `Done` merely because an issue closed or PR merged;
- expose confidential inputs/results;
- trigger consequential physical/engineering mutations unattended;
- replace exact-artifact handoffs with moving branch names;
- manufacture acceptance evidence.

Automate clerical consistency. Keep judgment and consequential authorization
explicit.

## 10. Non-software projects

The same structure works outside code:

| Software term | General project equivalent |
| --- | --- |
| Source file | Document, CAD model, dataset, plan, design asset |
| Test | Review checklist, measurement, experiment, simulation, rehearsal |
| Pull request | Controlled proposal/diff for review |
| Deployment | Publication, manufacturing release, field use, stakeholder delivery |
| Runtime validation | Lab test, stakeholder approval, legal check, real-data trial |
| Rollback | Restore prior approved artifact/version |

The essential pattern is still: bounded work contract, isolated change,
reviewable diff, explicit evidence, exact handoff, and durable history.

## 11. Decision records

For decisions that are expensive to reverse, record a short decision document:

```markdown
# Decision: <title>

- Status: proposed | accepted | superseded
- Date:
- Context:
- Decision:
- Alternatives considered:
- Consequences:
- Evidence that would trigger reconsideration:
```

Do not turn every small preference into bureaucracy. Record decisions when
future contributors would otherwise reopen the same trade-off without context.

## 12. Retrospective loop

After each stage, ask:

- Which assumption was wrong?
- Which evidence was most useful?
- What information was missing at handoff?
- Which repeated instruction belongs in `AGENTS.md`, a template, or a skill?
- Which process step added no value and should be removed?
- What should the next smallest uncertainty-reducing stage be?

Update the system from real friction. This is the “learning by doing” loop that
turns one project's workflow into a reusable method.

## 13. Packaging this method as a Codex skill

The method is a good skill candidate because it contains a repeatable workflow
and non-obvious handoff/evidence rules. A lean skill should contain:

```text
operate-github-project/
  SKILL.md
  agents/openai.yaml
  references/
    github-project-operating-system.md
```

`SKILL.md` should stay short and instruct the agent to:

- inspect or initialize the project's durable information architecture;
- create/review issue contracts and evidence-gated statuses;
- preserve exact handoffs across chats/environments;
- read the bundled reference when detailed templates are needed.

Do not put project-specific Ansys facts into the generic skill. Keep those in
this repository's `AGENTS.md` and Mechanical documentation.

Before creating the actual skill, choose whether it should be:

- global/personal under `~/.codex/skills` for every project; or
- project-local for testing and iteration before wider reuse.

The recommended path is project-local drafting, one or two real uses, then a
global personal skill after the method proves stable.
