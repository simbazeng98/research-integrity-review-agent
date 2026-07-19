# Materials Process Lineage Review

This offline workflow creates conservative sample-stage verification questions from human-curated structured records. It does not extract process steps from papers, images, or free text, and it does not infer author intent.

## Process stages

The declared lineage order is:

```text
preparation -> sonication or vortex -> filtration -> storage -> DLS -> deposition
```

Sonication and vortex are alternative operations at the same ordering level. A record may omit operations that were not used, but any supplied `stages` must remain in process order.

## Structured input

```yaml
sample_id: toy-dispersion-01
source_file: materials/toy_process_lineage.yml
location: sample lineage row 1
stages:
  - preparation
  - sonication
  - filtration
  - storage
  - dls
  - deposition
measurement_stage: after_filtration
distribution_basis: intensity_weighted
nominal_pore_nm: 220
hydrodynamic_diameter_nm: 1000
human_confirmed: true
```

Supported distribution bases are `intensity_weighted`, `volume_weighted`, `number_weighted`, and `z_average`. The measurement-stage relation is `before_filtration`, `after_filtration`, or `unknown`.

## Decision contract

| Context | Output |
| --- | --- |
| Measurement stage or distribution basis unknown | Low-risk missing-context record; no size comparison |
| DLS aliquot explicitly before filtration | No post-filtration comparison |
| DLS explicitly after filtration, basis known, diameter below the configured large-ratio threshold | No question |
| DLS explicitly after filtration, basis known, diameter at least three times the nominal pore by default | Low-risk verification question with `open_for_scoring: false` and `mrpi_eligible: false` |

The default ratio threshold is a conservative routing heuristic, not a physical law. It is configurable and must not be calibrated from a single paper or public discussion.

## Required alternative explanations

Every size-ratio question preserves these benign possibilities:

- nominal pore rating versus effective retention behavior;
- passage of soft or deformable particles;
- intensity-weighted emphasis of rare larger aggregates;
- aggregation after filtration during storage, transport, or DLS handling.

## Manual verification

Confirm that the pore rating and DLS result refer to the same sample lineage. Record the filter material and rating basis, the aliquot stage, the complete DLS distribution and weighting basis, and the storage or handling interval before measurement.

The output is a verification question only. It does not establish particle rigidity, retention efficiency, aggregation kinetics, intent, or responsibility, and it contributes no integrity MRPI weight.
