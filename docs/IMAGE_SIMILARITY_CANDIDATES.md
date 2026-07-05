# Image Similarity Candidates Documentation

This document describes the design, implementation, and verification guidelines for the Perceptual Image Similarity Candidate Detector introduced in v0.8.

## Scope of v0.8

The similarity checking subsystem is designed as an offline helper that flags visually similar pairs of images within the same package/folder.
1. **Perceptual Hashing (dHash/aHash):** Implemented using pure Python and Pillow. dHash constructs an 8-byte (64-bit) fingerprint based on horizontal gradients. aHash serves as the fallback for global average intensity matching.
2. **Hamming Distance Comparison:** The system computes the number of differing bits between hashes. By default, pairs with a Hamming distance $\le 6$ are flagged as similarity candidates.
3. **Contact Sheet Visualization:** Renders the matched candidate pairs side-by-side with dimensions, filenames, and Hamming distance details.

## Technical Limitations & Heuristic Thresholds

- **No Photoshop or Manipulation Detection:** The detector does not evaluate editing traces, splicing, cloning, Error Level Analysis (ELA), noise inconsistencies, resampling artifacts, or metadata tampering.
- **Local Scope Only:** v0.8 processes only images supplied in the local target folder (e.g. `examples/toy_image_package/images`). It does not run web search queries or query global reference databases.
- **Heuristic Threshold:** The Hamming distance threshold of $6$ is a heuristic threshold. Actual visual similarity can vary depending on image complexity, textures, and resolutions.

## False Positive Risks

Perceptual hashes summarize global visual structure. Consequently, the following items are highly prone to false positives:
1. **Low-texture microscopy fields:** Uniform cellular or tissue fields with similar background distribution.
2. **Schematic figures & diagrams:** Flowcharts, block diagrams, or data plots with identical white backgrounds and axis borders.
3. **Common scale bars/backgrounds:** Reused annotations, grids, or background structures.
4. **Simple synthetic patterns:** Simple geometric shapes on solid backdrops.

## Manual Verification Requirements

Similarity candidate flags are **only visual suggestions** for human review and do not constitute evidence of misconduct or intentional manipulation. To verify a signal, review:
1. **Original unprocessed image files:** High-resolution raw exports directly from instruments.
2. **Acquisition metadata:** Instrument logs, timestamps, temperature parameters, and software settings.
3. **Figure legends:** Check if the paper explicitly states that the panels represent intentional re-use, duplicate controls, or schematics.
4. **Source data:** Corresponding raw numeric measurements or spreadsheets.
5. **Author explanations:** Detailed feedback from authors regarding figure construction.
