# Psychometric Gaps Roadmap

This directory contains gap analysis documents for psychometric improvements that will enhance the scientific validity of AIQ's IQ scoring.

## Overview

These documents identify areas where the current implementation can be improved to align with professional psychometric standards. Each gap includes:

- Problem statement
- Current state analysis
- Proposed solutions
- Implementation considerations

## Gap Categories

### Item Analysis

| Gap | Description | Priority |
|-----|-------------|----------|
| [Empirical Item Calibration](./EMPIRICAL-ITEM-CALIBRATION.md) | Calibrate item difficulty from real response data | High |
| [Item Discrimination Analysis](./ITEM-DISCRIMINATION-ANALYSIS.md) | Measure how well items differentiate ability levels | Medium |
| [Distractor Analysis](./DISTRACTOR-ANALYSIS.md) | Analyze effectiveness of wrong answer choices | Low |

### Score Reliability

| Gap | Description | Priority |
|-----|-------------|----------|
| [Reliability Estimation](./RELIABILITY-ESTIMATION.md) | Calculate internal consistency (Cronbach's alpha) | High |
| [Standard Error of Measurement](./STANDARD-ERROR-OF-MEASUREMENT.md) | Provide confidence intervals around scores | High |

### Test Administration

| Gap | Description | Priority |
|-----|-------------|----------|
| [Time Standardization](./TIME-STANDARDIZATION.md) | Standardize timing across test administrations | Medium |
| [Cheating Detection](./CHEATING-DETECTION.md) | Detect anomalous response patterns | Medium |

### Scoring Model

| Gap | Description | Priority |
|-----|-------------|----------|
| [Domain Weighting](./DOMAIN-WEIGHTING.md) | Weight cognitive domains appropriately | Low |

## Implementation Status

- **Empirical Item Calibration**: In progress (see [implementation plan](../../plans/EMPIRICAL_CALIBRATION.md))
- All others: Planned for future phases

## Related Documentation

- [IQ Scoring Methodology](../IQ_SCORING.md) - Current scoring approach
- [Architecture Overview](../../architecture/OVERVIEW.md) - System design context
