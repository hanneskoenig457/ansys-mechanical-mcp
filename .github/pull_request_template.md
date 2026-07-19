## Scope

Closes #

Describe the single stage or prerequisite slice and its explicit non-goals.

## Safety And Engineering Assumptions

- Mutation boundary:
- Units and model assumptions:
- Confidential local inputs committed: no
- Existing project/output overwrite possible: no

## macOS Development Evidence

- [ ] Unit/fake tests passed
- [ ] In-process MCP tests passed where applicable
- [ ] Ruff passed
- [ ] Environment diagnostic passed
- [ ] `git diff --check` passed

Commands and results:

```text
<paste concise evidence>
```

## Windows Mechanical Evidence

- Exact commit for validation: `<full SHA or pending>`
- Mechanical/PyMechanical version: `<version or pending>`
- Live tool sequence and structured evidence: `<evidence or pending>`
- GUI/process/listener cleanup: `<evidence or pending>`
- [ ] Required licensed validation passed
- [ ] No Windows source edits were needed

Fake tests do not satisfy the Windows checklist. If live validation is not
required for this PR, explain why:

## Documentation And Handoff

- [ ] Relevant roadmap/API/architecture documentation updated
- [ ] Stage issue contains branch, exact commit, and remaining live assumptions
- [ ] No CAD, `.mechdb`, Workbench hierarchy, or solver output is present in the diff
