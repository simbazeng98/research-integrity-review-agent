from __future__ import annotations

import json
from pathlib import Path


PACKAGE_DIRECTORIES = (
    "metadata",
    "images",
    "tables",
    "pv",
    "raw_pv",
    "references",
    "documents",
)

PACKAGE_GUIDE = """# Local research-evidence review package

This folder stays local. Add only the paper materials and source data that you
are authorized to review.

## Start here

1. Put the DOI in `metadata/doi.txt`.
2. Put figures in `images/`, general tables in `tables/`, photovoltaic tables
   in `pv/`, and raw photovoltaic files in `raw_pv/`.
3. Open the inert `documents/*.example.*` templates. Copy only the templates
   you need to their active names after checking every source location and
   changing the relevant confirmation field to `true`.
4. Preview the plan with `python -m integrity_agent wizard --lang zh
   --package-dir <package>`.
5. Run `python -m integrity_agent review-package <package> -o <output>` and
   open the generated local dashboard.

## Human-confirmation gate

PDF, OCR, image, and model extraction may help locate text, but they must not
directly create findings. Keep draft claims and curve mappings unconfirmed until
a person checks the cited source location, sample, device variant, measurement
context, unit, and publication version.

The output is a set of candidate signals and verification requests. It is not a
truth or conduct verdict.
"""

CLAIM_EXAMPLE = {
    "claim_id": "replace-me-claim-001",
    "claim_type": "measurement_or_method",
    "value": None,
    "unit": None,
    "device_variant": "replace-me",
    "sample_id": "replace-me",
    "measurement_context": "replace-me",
    "source_document": "main_or_si_or_table",
    "source_version": "publisher-version-1",
    "location": "page_or_figure_or_table_or_row",
    "source_hash": "not_available",
    "human_confirmed": False,
}

DECAY_EXAMPLE = {
    "record_id": "replace-me-decay-001",
    "claim_id": "replace-me-decay-001",
    "decay_type": "trpl",
    "sample_id": "replace-me",
    "source_version": "publisher-version-1",
    "source_document": "fit_table",
    "source": "documents/decay_fit_records.jsonl",
    "location": "table_or_figure_location",
    "source_hash": "not_available",
    "reported_average": 1.0,
    "reported_unit": "us",
    "declared_formula": "amplitude_weighted",
    "components": [
        {"amplitude": 1.0, "lifetime": 0.5, "unit": "us"},
        {"amplitude": 1.0, "lifetime": 1.5, "unit": "us"},
    ],
    "human_confirmed": False,
}

VERSION_EXAMPLE = """manifest_version: '1'
target_doi: 10.1000/replace-me
events: []
"""

CURVE_EXAMPLE = """reconciliations:
  - source_table:
      path: tables/source.csv
      source_label: tables/source.csv
      location: source-data rows
      sample_id: replace-me
      source_version: publisher-version-1
    plot_table:
      path: tables/plot.csv
      source_label: tables/plot.csv
      location: plot-data rows
      sample_id: replace-me
      source_version: publisher-version-1
    mapping:
      source_x: time
      source_y: signal
      plot_x: time
      plot_y: signal
      x_axis_kind: time
    segment_similarity:
      human_confirmed_independent_curves: false
      minimum_window_points: 8
"""

LINEAGE_EXAMPLE = """records:
  - sample_id: replace-me
    source_file: materials/process-lineage.yml
    location: method_or_table_location
    stages:
      - preparation
      - filtration
      - dls
    measurement_stage: unknown
    distribution_basis: unknown
    nominal_pore_nm: 220
    hydrodynamic_diameter_nm: 220
    human_confirmed: false
"""


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def initialize_review_package(package_dir: Path | str) -> list[Path]:
    root = Path(package_dir)
    for relative_dir in PACKAGE_DIRECTORIES:
        (root / relative_dir).mkdir(parents=True, exist_ok=True)

    files = {
        Path("metadata/doi.txt"): "",
        Path("metadata/doi.example.txt"): "10.1038/s41563-020-0000-0\n",
        Path("PACKAGE_GUIDE.md"): PACKAGE_GUIDE,
        Path("documents/claims.example.jsonl"): (
            json.dumps(CLAIM_EXAMPLE, ensure_ascii=False) + "\n"
        ),
        Path("documents/version_manifest.example.yml"): VERSION_EXAMPLE,
        Path("documents/decay_fit_records.example.jsonl"): (
            json.dumps(DECAY_EXAMPLE, ensure_ascii=False) + "\n"
        ),
        Path("documents/curve_reconciliations.example.yml"): CURVE_EXAMPLE,
        Path("documents/materials_process_lineage.example.yml"): LINEAGE_EXAMPLE,
    }
    created: list[Path] = []
    for relative_path, content in files.items():
        target = root / relative_path
        if _write_if_missing(target, content):
            created.append(target)
    return created
