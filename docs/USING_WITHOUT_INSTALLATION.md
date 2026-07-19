# Use the review method without installing the project

The repository includes three portable skills and three copy-paste prompts. They preserve the same safety boundary as the CLI but do not require Python or this package to be installed.

This route is a set of agent instructions, not a bundled runner. The receiving
agent must already be able to read the supplied file formats (or ask you for a
safe conversion). Copying a skill does not install a spreadsheet engine, PDF
parser, OCR service, or network connector.

## Choose the smallest useful route

### Route A: paste one prompt

Use this when your agent supports ordinary chat instructions:

- [`review-a-paper-conservatively.md`](../prompts/review-a-paper-conservatively.md): inventory a paper package and build a human-confirmation queue.
- [`reconcile-cross-document-claims.md`](../prompts/reconcile-cross-document-claims.md): compare already confirmed claims across main text, SI, tables, and versions.
- [`review-perovskite-source-data.md`](../prompts/review-perovskite-source-data.md): review supplied photovoltaic and perovskite source tables.

Open a prompt in GitHub or any free text editor, copy the full content, paste it into your agent, then attach or place only the files you want reviewed in that agent's workspace.

### Route B: copy a reusable skill

Use this when your agent supports `SKILL.md` folders:

- [`triage-research-evidence`](../skills/triage-research-evidence/SKILL.md): non-judgmental intake and claim confirmation.
- [`check-research-consistency`](../skills/check-research-consistency/SKILL.md): deterministic and cross-document checks.
- [`write-safe-integrity-report`](../skills/write-safe-integrity-report/SKILL.md): publication-safe reporting and final safety gate.

Copy the complete named folder into your agent's skills directory. Each skill works on its own; the optional method reference in `check-research-consistency` adds compact formulas and false-positive controls.

## Recommended sequence

```text
triage-research-evidence
        -> human confirms atomic claims
check-research-consistency
        -> candidate evidence records
write-safe-integrity-report
        -> pass/blocked publication gate
```

Do not skip human confirmation by treating model or OCR extraction as a verified source. The skills produce candidate signals and verification requests; they do not decide whether a paper or person is trustworthy.

## Privacy checklist

- Keep papers and source data local unless you deliberately choose a service that uploads them.
- Remove authentication material, personal data, private correspondence, and local absolute paths before sharing a report.
- Share source labels, locations, hashes, calculations, counter-evidence, and limitations instead of full copyrighted source text.
- Keep cost, scale-up, and manufacturability questions outside research-integrity scoring.
