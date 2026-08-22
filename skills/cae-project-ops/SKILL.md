---
name: cae-project-ops
description: Structure and maintain CAE and engineering projects so their current state, evidence, files, decisions, and ongoing GitHub work remain understandable across people, AI agents, tools, and sessions. Use when initializing or reorganizing a CAE project, deciding where CAD, measurements, papers, scripts, results, and documentation belong, closing out a substantial task, cleaning project clutter, maintaining linked Markdown/Obsidian navigation, or managing issue/PR/project handoffs. Do not use merely to perform an isolated simulation or edit one unrelated file.
---

# CAE Project Operations

Keep four kinds of truth separate:

- project Markdown records the current, durable state and the evidence behind it;
- GitHub issues and Projects record proposed or active work and its status;
- commits and pull requests record reviewable changes;
- chat is an execution interface and ends with a concise handoff, not the only record.

## Select the operating mode

### Understand or audit an existing project

Read the root `README.md`, repository instructions, linked documentation, and
Git status before judging the structure. Inventory files and links. Run
`scripts/audit_project.py <project-root>` when a structural audit is useful.
It is read-only. Do not reorganize or delete files unless the user requested
that change and the role of each affected artifact is understood.

### Initialize or normalize a project

Read [references/project-structure.md](references/project-structure.md). Use
the smallest structure that fits the project; do not create every optional
folder. The root `README.md` is the human/agent dashboard. Give every other
Markdown file a descriptive, unique filename so Obsidian graph nodes remain
recognizable.

Use standard relative Markdown links rather than Obsidian-only wikilinks when
the same files should work in GitHub, Codex, Claude, and Obsidian. Keep source
artifacts separate from generated artifacts, but respect application-imposed
locations such as Workbench-linked CAD and project databases.

### Execute or close a substantial task

Before changing files, establish the task contract and preserve unrelated
work. After the implementation or analysis:

1. verify the result proportionally to its risk;
2. update documentation affected by changed behavior, structure, interfaces,
   assumptions, decisions, validation, or completed subtask status;
3. inventory new and modified files and classify them;
4. flag or remove only clearly disposable task-generated clutter, preserving
   user artifacts and recoverable evidence;
5. update the issue/PR/Project handoff when GitHub is in use;
6. report changed artifacts, checks, remaining uncertainty, and the next
   action in the final response.

Read [references/documentation-contract.md](references/documentation-contract.md)
when creating, splitting, linking, or cleaning documentation.

### Coordinate ongoing work in GitHub

Read [references/github-workflow.md](references/github-workflow.md) when work
spans sessions, changes an engineering model, needs validation, or has multiple
independent tasks. Small housekeeping changes do not need ceremonial issues.
Do not create a remote repository or choose public/private visibility without
user authorization.

## Safety and scope

- Documentation is evidence, not proof by assertion. Separate observed,
  inferred, planned, and validated claims.
- A completed issue or merged PR does not prove domain or solver validity.
- Never commit credentials, confidential inputs, licensed databases, bulky
  generated solver state, or machine-private configuration without an explicit
  storage decision.
- Prefer archiving with a reason over deleting a failed approach whose lesson
  is still valuable. Do not use an archive as an unbounded dumping ground.
- Do not rewrite stable documentation merely to make it stylistically uniform.
  Update it when the project truth or navigation changed.
