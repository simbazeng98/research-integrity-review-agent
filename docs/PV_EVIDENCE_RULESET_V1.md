# Photovoltaics (PV) Evidence Ruleset v1

> [!IMPORTANT]
> **Safety Notice & Disclaimer**
> - The PV evidence ruleset is a taxonomy of evidence completeness and consistency signals, **not an automatic misconduct detector**.
> - Surfaced signals do **not** confirm, verify, or prove research misconduct, data fabrication, or fraud.
> - Surfaced signals require **manual verification** and thorough **source/raw data** review to determine validity.

This document describes the design, purpose, structure, and usage of the PV Evidence Ruleset v1 taxonomy.

## Purpose and Scope

The v1 taxonomy is designed to evaluate the completeness of solar cell and materials characterization reporting and the consistency of physical device metrics within paper table packages. It provides standardized candidate signals, questions for manual reviewers, and alternative benign explanations to facilitate objective evidence reviews.

It does **not** assert or verify misconduct. It serves as a checklist and reference helper for domain-expert human reviewers.

## 5 Taxonomy Categories Covered

1. **J-V Reporting**: Scan direction, hysteresis, mask area definition, light intensity, stabilized power output (SPO), and maximum power point (MPP) tracking configuration.
2. **EQE/J-V**: Mismatches between integrated EQE Jsc and J-V simulator Jsc, wavelength spectrum range, standard AM1.5G reference database usage, and reflection/parasitic absorption corrections.
3. **Stability**: ISOS protocol designations, UV dose, humidity levels, temperature, encapsulation details, and continuous tracking versus dark shelf storage tracking modes.
4. **Tandem**: Subcell bandgap completeness (top/bottom), current matching in series-connected 2T junctions, spectral mismatch adjustments, aperture area, shadow mask presence, and 2T/4T terminal configuration physical consistency.
5. **Materials Characterization**: Composition/stoichiometry details, Self-Assembled Monolayer (SAM)/interface treatment conditions, Atomic Layer Deposition (ALD) or TCO sputter damage mitigation, and XRD/SEM/PL/UPS/XPS instrument and measurement metadata.

## How to Run the Export CLI

You can export the complete ruleset taxonomy containing all 26 rules with their descriptions, required evidence, manual verification questions, and benign alternatives using the following CLI command:

```bash
python -m integrity_agent pv-ruleset-export
```

### Outputs

The export command generates two files under the `outputs/pv_ruleset_v1/` directory by default:
- **JSON Format**: `outputs/pv_ruleset_v1/pv_evidence_ruleset_v1.json` (for programmatic ingestion or tool indexing)
- **Markdown Format**: `outputs/pv_ruleset_v1/pv_evidence_ruleset_v1.md` (for human reading and offline reference)

You can specify a custom output directory using the `-o` or `--output-dir` option:
```bash
python -m integrity_agent pv-ruleset-export -o custom_output_dir/
```

## Limitations

- **Tabular Scope**: The ruleset operates primarily on parsed tabular source data (CSV, TSV, XLSX, Markdown tables). It does not automatically parse unstructured text, image plots, or raw binary instrument sweep log formats.
- **Header Dependency**: Automatic schema inference relies on standard terminology and keyword profiling. Custom, non-standard, or non-English column headers may require manual field mapping.
- **Context Dependency**: Inconsistencies or omissions do not imply errors; they may be explained by experimental setup, instrument limitations, or documentation located elsewhere in the paper's supplementary files.
