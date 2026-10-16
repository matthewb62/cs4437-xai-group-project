# Prompt Log: 2026-10-02

**Tool:** Claude Code (Claude Opus 5.5). **Specification:** `person_a.md`.

## 2026-10-02: Planning (claude.ai, "Model completion requirements")

1. Asked for download requirements and a task split (after pasting the old `download_data.py` stub):
   > can you add this to the list of requirements please as i need a list of requirements that split the tasks needed in 2 so that different users know what they need to do. Can you have one user completing the data downloading script and then split the remaining tasks in 2 please so that the model can be completed.

2. Corrected the split to two people:
   > there is only 2 people so one person is taking the download script and half the tasks and the other person is taking the other half of the tasks

3. Asked for Person A's tasks as a file for Claude Code (produced `person_a.md`):
   > give me the tasks of person 1: (download script person) as a .md file please so that i can feed it into Claude code


## Implementation (Claude Code)

1. Produce a commit-by-commit implementation plan from `person_a.md`.
2. Implement the skeleton Commit 1 only (shared configuration and pinned requirements).
3. Read person_a.md and implement src/download_data.py (D1–D13). Do the price download first and show me the D11 summary before the rest. Report pass/fail by requirement ID when done.