# Documentation contract

## One purpose per artifact

| Artifact | Durable responsibility |
| --- | --- |
| Root `README.md` | Purpose, current validated state, key limitations, and navigation |
| `AGENTS.md` | Project-specific instructions, permissions, and safety boundaries |
| Model/method documents | Physics, inputs, assumptions, implementation, and known limits |
| Validation document | Exact artifact/version, environment, procedure, observations, and outcome |
| Decision record | Context, chosen option, alternatives, consequences, and date |
| Workflow-stage document | Inputs, executable method, outputs, checks, and runtime location |
| GitHub issue | Proposed/active work contract and acceptance criteria |
| Pull request | Reviewable delta and its evidence |
| GitHub Project | Portfolio status and handoff state |

Avoid maintaining the same changing status in both a local roadmap and a
GitHub issue list. Local files may record strategic direction and stable
non-goals; GitHub owns the actionable backlog when it is enabled.

## Linked Markdown and Obsidian

- Use descriptive filenames such as `geometry-workflow.md` rather than many
  files all named `README.md`. Obsidian's graph normally labels nodes by the
  filename, so duplicate names destroy context.
- Connect the root dashboard to every major document using standard relative
  Markdown links.
- Add a link back to the dashboard or parent index from leaf documents when it
  improves navigation. Do not create links solely to make the graph look busy.
- Prefer repository-relative paths and avoid machine-specific absolute links
  in tracked documentation.
- Keep one canonical copy. Obsidian is a view over the project Markdown, not a
  separate second-brain copy that can drift.

## Synchronization triggers

Update or remove affected documentation in the same task when any of these
changes:

- observable behavior or user operation;
- project structure or artifact location;
- public interface, script invocation, dependency, or environment assumption;
- engineering input, model assumption, decision, or known limitation;
- validation evidence or the confidence that may legitimately be claimed;
- completion, cancellation, or supersession of a documented subtask;
- accumulated task-generated clutter that obscures the active state.

Do not touch unrelated documents after a small internal refactor whose public
behavior and project understanding are unchanged.

## Task closeout

Before declaring completion:

1. inspect Git status or the equivalent file inventory;
2. classify every new artifact as source, input, intermediate, evidence,
   deliverable, private state, or disposable clutter;
3. update links and the smallest set of affected documents;
4. remove or archive disposable artifacts only when ownership and recovery are
   clear;
5. record checks and remaining uncertainty;
6. provide a concise handoff that names important files and the next action.

