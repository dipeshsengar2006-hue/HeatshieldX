# AGENTS.md — Hackathon Project Rules

## Source of truth
Read docs/SRS.md and docs/PLAN.md before any task. Do not invent features outside them.

If requirements are ambiguous or missing, list them and ask. Do not guess silently.

## Stack (do not change without my approval)
Python (Flask or FastAPI) + HTML + CSS + vanilla JavaScript. Jinja templates are fine.
If another technology is genuinely required, STOP and ask before changing anything.
Minimal dependencies. No frameworks, microservices or abstractions the requirements don't need.

## Quality bar
Production-quality, not a prototype:
- Clear folder structure (routes / services / models / templates / static), small focused modules
- Input validation and clear error handling on every endpoint and form
- Loading, empty and error states in the UI
- Responsive layout (mobile, tablet, desktop), accessible markup, consistent design system via CSS variables
- No hardcoded secrets. Use environment variables, provide `.env.example`, keep `.env` in `.gitignore`
- A README with setup and run instructions

## Workflow
One phase at a time: implement → test → review → fix → verify.
Each phase must leave the app in a working, runnable state.
Never claim something works unless you actually ran it. Show the command and its result.
Do NOT run `git commit` or `git push` unless I explicitly ask. When a phase is stable, say "READY FOR GIT PUSH" and suggest a commit message.

## Reporting (concise, no play-by-play)
End every task with:
- Status per item: Implemented / Partially Implemented / Not Implemented / Blocked / Needs Decision
- How to run and test it
- Known issues and risks
- Suggested commit message

## Do not
Refactor unrelated code, add unrequested features, add dependencies without saying why, or make cosmetic changes outside the current phase.