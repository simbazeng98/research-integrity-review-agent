# Image Evidence Intake Documentation

This document describes the design, scope, boundaries, and validation requirements for the Image Evidence Intake subsystem introduced in v0.7.

## Scope of v0.7

The current version implements:
1. **File Manifest Scanning:** Computes file-level SHA256 hashes and reads image dimensions (width, height), format, and colour mode using Pillow.
2. **Exact Duplicate Checking:** Grouping images purely by SHA256 hashes to detect exact file-level duplication.
3. **Contact Sheet Visualization:** Renders a static HTML gallery allowing manual inspection of the extracted figures and visually marking duplicate groups.

## Important Definitions & Safety Boundaries

- **Exact duplicate does not equal image manipulation:** Detecting two identical image files only indicates that the same file is reused (e.g., duplicated across panel assemblies, reused control panels, or multiple exports of the same illustration). It **does not prove misconduct or intent to deceive**.
- **pHash / SSIM / ORB / ELA are Future Work:** The current system does not perform near-duplicate, perceptual hashing, scale-invariant feature extraction (like ORB), structural similarity index (SSIM), or Error Level Analysis (ELA).
- **PDF Extraction is NOT Figure Segmentation:** Extracting raw image streams from PDFs is a fallback utility. It cannot guarantee panel-level slicing (A, B, C panels) or segment nested sub-figures.

## Manual Verification Requirements

Image evidence findings are candidate signals that **must be manually reviewed** by human editors. Verification requires:
1. **Original acquisition files:** Raw, uncompressed, high-resolution original image captures (e.g., raw camera exports, TIF, TIFF).
2. **Acquisition metadata:** Original instrument software export metadata, timestamp parameters, and camera settings.
3. **Figure legends:** Explicit descriptions in the paper identifying whether panels contain intentionally reused or duplicated control elements.
4. **Author explanations:** Clarifications from the researchers regarding figure assembly and layout choices.
5. **Source data:** Corresponding numeric datasets or spreadsheets associated with the experimental measurements.

## Dependencies

- **Pillow (PIL):** Required for extracting image dimensions (width, height), formats, and colour modes. Declared as a dependency in `pyproject.toml`.

