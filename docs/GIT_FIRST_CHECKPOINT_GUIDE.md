# Git First Checkpoint Guide

This project is currently not a git repository. Do not initialize git until the private-data boundary has been reviewed deliberately.

## Why the First Checkpoint Matters

The first checkpoint defines what becomes tracked history. Once private or generated files are tracked, later `.gitignore` changes do not remove them from history. A careful first checkpoint prevents private corpus leaks, cache noise, and generated-output churn from becoming part of the repository.

## Critical Rule: `.gitignore` Is Not Retroactive

`.gitignore` prevents new untracked files from being added accidentally. It does not untrack files already staged or committed. If a private file appears in `git status --short` after staging, stop and unstage it before committing.

## Never Stage These Categories

- Private corpus directories and local-only sentinels.
- ASR transcripts, chunk notes, screenshots, audio/video streams, comments, or danmaku.
- Real source data, real figures, papers under review, PDFs, DOCX, XLS/XLSX/XLSM, CSV/TSV raw data dumps.
- Test/runtime caches such as `.pytest_cache/`, `.test_cache*/`, `.cache/`, and generated `outputs/` artifacts.
- Local machine paths, credentials, cookies, API keys, or secret config files.

## First Checkpoint Commands

Run from the project root only after tests and smoke checks pass:

```bash
cd path/to/research-integrity-review-agent

git init
git config core.quotepath false

git status --ignored --short
```

Review ignored files first. Confirm private corpus, caches, real data, and generated outputs are ignored.

Then stage and inspect:

```bash
git add .
git status --short
```

Before committing, manually review staged files. On a normal first checkpoint, staged files should be source code, docs, tests, examples, and curated public knowledge-base artifacts only.

If a private/generated file is staged, unstage it before continuing:

```bash
git restore --staged <path>
```

Commit only after review (e.g., for v0.2.0, or historically v0.12-boundary-hardened):

```bash
git commit -m "v0.2.0 unified evidence runner with boundary fixes and bilingual wizard"
git tag v0.2.0
```

## Manual Review Before `git commit`

- Confirm no private corpus files are staged.
- Confirm no real data, papers, PDFs, workbooks, or raw measurement folders are staged.
- Confirm no generated `outputs/` artifacts are staged unless intentionally curated documentation has been moved elsewhere.
- Confirm docs and reports do not contain local absolute paths.
- Confirm command output paths are repo-relative where user-visible.
- Confirm release checks in `docs/RELEASE_READINESS.md` have passed.

## If Unsure

Stop before `git commit`. It is safer to delay the first checkpoint than to create history containing private or generated files.
