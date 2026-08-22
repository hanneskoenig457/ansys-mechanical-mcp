# Proportionate GitHub workflow

GitHub owns progress; repository Markdown owns durable project truth.

## When to create work items

Use an issue when work spans sessions, changes a model or workflow, has a
decision or validation gate, or contains multiple acceptance criteria. Skip an
issue for a tiny typo or obvious housekeeping change that can be explained by
one commit.

Use one independently reviewable branch and normally one pull request per
substantial issue. A GitHub Project becomes useful when several issues are
active, ordered, blocked, or handed between people/agents; do not create a
board for a single trivial task.

## Issue contract

Each executable issue records:

- context and desired outcome;
- scope and explicit non-goals;
- inputs, confidentiality, and allowed mutations;
- observable acceptance criteria;
- dependencies and responsible next role/environment;
- required documentation, cleanup, and validation evidence.

Ideas that are not ready for implementation still belong in a bounded idea or
decision issue. Label them accordingly; do not inflate the committed roadmap.

## Evidence-based status

Recommended states are `Backlog`, `Ready`, `In progress`, `In review`, `Ready
for validation`, `Blocked`, and `Done`. Status describes evidence, not a
percentage or an agent's confidence.

Post updates only at meaningful transitions: work started, a decision or input
is required, review/validation is ready, validation returned, or work is done.
Do not mirror terminal logs into issue comments.

## Pull request and handoff

A PR states scope, changed artifacts, checks, remaining validation, and the
issue it advances. A merged PR proves integration, not solver, experimental,
or domain validity.

Every cross-session handoff is recorded twice:

1. durable evidence in the issue or PR;
2. a short copy-ready final chat response naming the exact branch/commit or
   artifact, what is verified, what is not, and the next action.

Do not force-push an exact commit already handed to another environment for
validation. If it changes, explicitly invalidate and replace the old target.
