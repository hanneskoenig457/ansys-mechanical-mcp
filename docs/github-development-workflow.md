# GitHub Development And Machine Handoff

## Source Of Truth

GitHub issues are the durable work orders and evidence records for this
repository. Chat messages and copied prompts may help start a session, but they
must not be the only location of scope, dependencies, acceptance criteria, or
live-validation results.

The steady-state thermal parent issue owns the ordered roadmap. Each stage has
one child issue and normally one implementation pull request. The repository
documentation defines the invariant rules; issue bodies define the current
stage; comments carry timestamped handoff evidence.

## Machine Roles And Statuses

Use these handoff states in the GitHub Project field named `Handoff`:

| State | Meaning | Responsible environment |
| --- | --- | --- |
| `Backlog` | Ordered but not ready; a dependency is open | Neither |
| `Ready for Mac` | Scope and dependencies are complete | macOS development machine |
| `In Development` | Branch exists and implementation/tests are in progress | macOS development machine |
| `Ready for Windows` | Reviewed exact commit is available for licensed validation | Windows Mechanical machine |
| `In Validation` | Exact commit and prerequisites are being checked live | Windows Mechanical machine |
| `Done` | Development and required Windows gates both passed | Neither |

Only Stage 1 becomes `Ready for Mac` initially. A later stage remains `Backlog`
until its predecessor is `Done` and its own issue contract is reviewed. Status
changes are meaningful handoffs, not estimates of percent complete.

## Issue Contract

Every stage issue must identify:

- parent roadmap and predecessor dependency;
- engineering objective and explicit non-goals;
- mutation and safety boundary;
- intended MCP/API contract;
- macOS implementation and fake-test acceptance criteria;
- Windows live prerequisites, steps, acceptance criteria, and cleanup;
- required documentation changes;
- current branch, exact commit, pull request, and evidence links.

Use `.github/ISSUE_TEMPLATE/thermal-stage.yml` for additional stages or
follow-up slices. Never paste confidential CAD or solver artifacts into an
issue. Safe evidence means structured text with sensitive paths and geometry
details minimized.

## Branch And Pull Request Contract

Normal implementation work starts on the Mac from an up-to-date `main`:

```text
agent/thermal-stage-<n>-<short-purpose>
```

One pull request should close one stage issue unless the issue explicitly
defines smaller prerequisite PRs. The pull request remains draft while the Mac
gate is incomplete. Before Windows handoff it records the exact head commit,
all non-live checks, and all remaining live assumptions.

Do not force-push a commit already handed to Windows. If development changes,
post a new exact commit and invalidate the earlier validation target. Do not
merge a stage as functionally complete until the required Windows evidence is
attached. Documentation/tracking PRs that contain no Mechanical feature may be
merged after their ordinary CI and review gate.

## Handoff Comment Templates

Development-to-Windows:

```markdown
## Ready for Windows

- Branch: `<branch>`
- Commit: `<full SHA>`
- PR: #<number>
- Mac checks: `<commands and results>`
- Not live validated: `<assumptions>`
- Local input/output prerequisites: `<safe relative details>`
- Allowed mutation: `<exactly bounded action>`
- Tool order: `<ordered calls>`
- Expected evidence: `<fields and cleanup proof>`
```

Windows-to-development:

```markdown
## Windows evidence

- Commit validated: `<full SHA>`
- Mechanical/PyMechanical: `<versions>`
- Session/transport: `<safe structured summary>`
- Tool results: `<safe structured evidence>`
- GUI/process/listener before and after: `<evidence>`
- Result: `passed | failed | blocked`
- Reproduction/discrepancy: `<exact order and error>`
- Source changed on Windows: `no` (normal path)
```

## Automation Boundary

Automation may create the roadmap, add issues to the project, populate labels,
check required fields, and move an item after objective repository events.
Automation must not:

- infer successful licensed validation from CI;
- move an item to `Done` merely because a PR merged;
- expose or upload local CAD/results;
- trigger Mechanical model mutations unattended;
- replace the exact-commit handoff with a moving branch name.

The repository templates make the workflow reproducible on both machines even
when GitHub Project automation is unavailable. `docs/live-validation-workflow.md`
remains authoritative for Mechanical session and listener safety.

New issues created through the thermal issue form are automatically labelled

- `area:thermal`;
- `handoff:backlog`;
- `validation:windows-required`.

Handoff labels are otherwise changed deliberately when their evidence gate is
met. The workflow never infers `Done` from a close or merge event.

## Minimal Session Starters

After the tracking PR is merged, a new Codex session should need only the issue
number and machine role. For example:

```text
Mac: Synchronisiere ansys-mechanical-mcp und bearbeite Issue #<n> gemäß
AGENTS.md und den verlinkten Repository-Dokumenten. Lies Issue-Body und aktuelle
Handoff-Kommentare selbst; implementiere nur den Mac-Gate-Scope.

Windows: Synchronisiere ansys-mechanical-mcp auf den exakten in Issue #<n>
genannten Commit und führe ausschließlich dessen Windows-Gate gemäß AGENTS.md
und docs/live-validation-workflow.md aus. Poste die sichere Evidenz zurück ins
Issue; ändere im Normalfall keinen Quellcode.
```

The operator therefore coordinates by issue number and explicit machine role;
the issue and repository supply the detailed instructions.
