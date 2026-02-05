# TASK-873: CAT Simulation Engine Implementation Plan

## Overview

Build a simulation engine to validate CAT algorithm performance using both the external `catsim` library and the internal CAT engine. This is a validation tool for research and quality assurance, not production-facing code.

## Strategic Context

### Problem Statement

We need to validate that our CAT implementation produces high-quality adaptive tests across the full ability range. Specifically, we must confirm that:
- Tests converge to the target SE threshold (0.30) efficiently
- Item selection works correctly across all ability levels
- Content balancing constraints are satisfied
- The stopping rules function properly
- Our internal engine produces comparable results to the established `catsim` library

### Success Criteria

**Primary validation metrics**:
- ≥90% of examinees reach SE < 0.30 within 15 items
- Mean test length: 8-12 items (efficient adaptive testing)
- Content balance: All domains represented in ≥90% of tests
- RMSE < 0.40 (ability estimation accuracy)
- Mean bias < 0.05 (systematic error check)

**Comparative validation**:
- Internal engine produces results within 10% of `catsim` baseline
- No systematic differences across ability quintiles

### Why Now?

We've just completed the full CAT stack (TASK-864 through TASK-872). Before deploying to production, we need empirical validation that the system performs correctly across all ability levels and edge cases.

## Technical Approach

### High-Level Architecture

```
SimulationEngine
├── generate_examinees(N, theta_distribution)
├── run_simulation(engine_type="internal"|"catsim")
│   ├── For each examinee:
│   │   ├── Initialize CAT session with true theta
│   │   ├── Select items until stopping
│   │   └── Record metrics
│   └── Return SimulationResult
└── generate_report(result)
    ├── Compute aggregate metrics
    ├── Break down by ability quintile
    ├── Generate comparison tables
    └── Create visualizations (optional)
```

### Key Design Decisions

**1. Dual-engine architecture**
- **Internal engine**: Use existing `CATSessionManager` with deterministic item selection (randomesque_k=1)
- **catsim engine**: Use `catsim.simulation.Simulator` with comparable configuration
- **Why**: Validate our implementation against established baseline; detect systematic errors

**2. Deterministic item selection for simulation**
- Disable randomesque selection (set k=1) to ensure reproducible results
- Seed RNG for controlled randomness in response generation
- **Why**: Reproducibility is critical for validation and debugging

**3. Simulate response patterns, not just theta**
- Generate responses using 2PL IRT probability: P(correct|theta) = 1 / (1 + exp(-a(theta - b)))
- Add realistic variability via probabilistic sampling
- **Why**: Tests the full CAT pipeline, not just ability estimation in isolation

**4. Metrics collection per-examinee**
- Track: test length, final SE, final theta estimate, bias, domain coverage
- Aggregate across examinees for summary statistics
- **Why**: Enables quintile analysis and detection of edge-case failures

**5. Simple text-based reporting**
- Markdown table output with quintile breakdowns
- Optional matplotlib visualizations (not required for Phase 1)
- **Why**: Keep implementation simple; focus on validation, not presentation

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| catsim API incompatibility | Can't run comparison | Document incompatibilities; run internal-only validation if needed |
| Item bank too small for exposure control | Biased results | Use full calibrated item bank; flag if N_items < 100 |
| Simulation too slow (1000+ examinees) | Long validation cycles | Optimize inner loop; consider parallelization if needed (Phase 2) |
| Theta distribution mismatch | Invalid comparison | Use same theta distribution for both engines |

## Implementation Plan

### Phase 1: Core Simulation Infrastructure (3-4 hours)

**Goal**: Basic single-engine simulation with the internal CAT engine

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create `SimulationConfig` dataclass | None | 20min | N, theta_range, seed, stopping config |
| 1.2 | Create `ExamineeResult` dataclass | None | 15min | theta_true, theta_est, se, num_items, bias, domain_coverage |
| 1.3 | Create `SimulationResult` dataclass | 1.2 | 15min | config, results: List[ExamineeResult], summary stats |
| 1.4 | Implement `generate_examinees()` | 1.1 | 30min | Sample N thetas from uniform[-3, 3] or normal(0,1) |
| 1.5 | Implement `simulate_response()` | None | 30min | 2PL IRT probability with seeded RNG |
| 1.6 | Implement `run_internal_simulation()` | 1.2, 1.4, 1.5 | 90min | Full CAT loop using CATSessionManager |

**Key implementation details for 1.6**:
- Load item bank from database (calibrated items only)
- Initialize `CATSessionManager` with deterministic settings
- For each examinee:
  - Initialize session with theta_true as prior (simulates perfect prior knowledge)
  - Loop: select item → simulate response → process → check stopping
  - Record final metrics
- Return `SimulationResult`

### Phase 2: catsim Integration & Comparison (2-3 hours)

**Goal**: Add catsim baseline and comparative metrics

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Implement `build_catsim_item_bank()` | None | 30min | Convert DB items to catsim ItemBank format |
| 2.2 | Implement `run_catsim_simulation()` | 1.4, 2.1 | 60min | Use catsim.simulation.Simulator |
| 2.3 | Implement `compare_engines()` | 1.3, 2.2 | 45min | Compute delta metrics between internal/catsim |
| 2.4 | Add quintile breakdown | 1.3 | 30min | Split results by ability: [-3,-1.5], [-1.5,-0.5], [-0.5,0.5], [0.5,1.5], [1.5,3] |

**Key implementation details for 2.2**:
- Configure catsim with matching parameters:
  - Initializer: theta=0, se=1 (or use true theta)
  - Selector: MaximumFisherInformation
  - Estimator: EAP (or MLE if EAP unavailable)
  - Stopper: SE threshold, min/max items
- Handle catsim API differences gracefully
- Return results in same `ExamineeResult` format

### Phase 3: Reporting & Validation (1-2 hours)

**Goal**: Generate actionable validation reports

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Implement `calculate_summary_stats()` | 1.3 | 30min | Mean/median items, mean SE, mean bias, RMSE, convergence rate |
| 3.2 | Implement `generate_report_markdown()` | 2.4, 3.1 | 45min | Table format with overall + quintile breakdowns |
| 3.3 | Add CLI entry point | 3.2 | 30min | `python -m app.core.cat.simulation --n 1000 --output report.md` |

**Report format**:
```markdown
# CAT Simulation Report

## Configuration
- N: 1000 examinees
- Theta range: [-3.0, 3.0]
- Distribution: uniform
- Seed: 42

## Overall Results

| Engine | Mean Items | Median Items | Mean SE | Mean Bias | RMSE | Converged % |
|--------|-----------|--------------|---------|-----------|------|-------------|
| Internal | 10.2 | 10 | 0.28 | -0.02 | 0.35 | 92% |
| catsim | 10.5 | 10 | 0.27 | -0.01 | 0.34 | 93% |

## By Ability Quintile

### Very Low (-3.0 to -1.5)
[Similar table...]

### Exit Criteria Status
- ✓ Mean SE < 0.30: 0.28
- ✓ Convergence ≥90%: 92%
- ✓ Mean items ≤15: 10.2
- ✗ RMSE < 0.40: 0.35
```

### Phase 4: Testing (2 hours)

**Goal**: Comprehensive test coverage

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Test `generate_examinees()` | 1.4 | 20min | Distribution properties, seed reproducibility |
| 4.2 | Test `simulate_response()` | 1.5 | 30min | Response probability correctness |
| 4.3 | Test `run_internal_simulation()` | 1.6 | 45min | Small N=10 test, convergence checks |
| 4.4 | Test quintile breakdown | 2.4 | 20min | Boundary cases |
| 4.5 | Test report generation | 3.2 | 25min | Format validation, edge cases (N=0, N=1) |

**Test strategy**:
- Use small item banks (10-20 items) for fast tests
- Use small N (5-10 examinees) for integration tests
- Mock database queries for unit tests
- Use fixed seeds for reproducible test cases

## Open Questions

1. **Prior specification**: Should we initialize CAT sessions with the true theta (perfect prior) or theta=0 (uninformed prior)?
   - **Recommendation**: Use theta=0 for more realistic simulation (tests cold-start performance)

2. **Response time simulation**: Should we simulate response times or ignore them?
   - **Recommendation**: Ignore for Phase 1; add in Phase 2 if needed for validity analysis

3. **Exposure control**: Should simulations use randomesque selection?
   - **Recommendation**: No—use deterministic selection (k=1) for reproducibility

4. **Visualization**: matplotlib vs. text-only reports?
   - **Recommendation**: Text-only for Phase 1; add optional plots if time permits

## Implementation Notes

### File Structure

```
backend/app/core/cat/simulation.py
backend/tests/core/test_cat_simulation.py
```

### Key Classes

```python
@dataclass
class SimulationConfig:
    n_examinees: int
    theta_distribution: str  # "uniform" or "normal"
    theta_range: Tuple[float, float]
    seed: Optional[int]
    se_threshold: float
    min_items: int
    max_items: int

@dataclass
class ExamineeResult:
    examinee_id: int
    theta_true: float
    theta_estimate: float
    theta_se: float
    num_items: int
    bias: float  # theta_estimate - theta_true
    domain_coverage: Dict[str, int]
    converged: bool  # se < se_threshold

@dataclass
class SimulationResult:
    config: SimulationConfig
    engine_type: str
    results: List[ExamineeResult]
    # Summary stats computed on-demand
```

### Key Functions

```python
def generate_examinees(config: SimulationConfig) -> List[float]:
    """Generate true theta values for N examinees."""

def simulate_response(theta: float, a: float, b: float, rng: random.Random) -> bool:
    """Simulate a response using 2PL IRT probability."""

def run_internal_simulation(
    config: SimulationConfig,
    item_bank: List[Question]
) -> SimulationResult:
    """Run simulation using internal CAT engine."""

def run_catsim_simulation(
    config: SimulationConfig,
    item_bank: List[Question]
) -> SimulationResult:
    """Run simulation using catsim library."""

def calculate_summary_stats(result: SimulationResult) -> Dict[str, Any]:
    """Compute mean/median/RMSE/bias across examinees."""

def breakdown_by_quintile(result: SimulationResult) -> Dict[str, SimulationResult]:
    """Split results into 5 ability ranges."""

def generate_report_markdown(
    internal_result: SimulationResult,
    catsim_result: Optional[SimulationResult] = None
) -> str:
    """Generate markdown report with tables."""
```

### Dependencies

**Existing modules**:
- `app.core.cat.engine.CATSessionManager`
- `app.core.cat.item_selection.select_next_item`
- `app.models.models.Question`
- `app.core.config.settings`

**External libraries**:
- `catsim==0.20.0` (already in requirements.txt)
- `numpy` (via scipy, already available)
- `random` (stdlib)

**Database**:
- Query calibrated items: `Question.query.filter(Question.irt_discrimination.isnot(None))`

## Appendix: catsim API Reference

Based on inspection of `catsim==0.20.0`:

```python
from catsim.simulation import Simulator
from catsim import irt

# Create item bank: (a, b, c) tuples (c=guessing param, use 0 for 2PL)
items = numpy.array([[a1, b1, 0], [a2, b2, 0], ...])

# Run simulation
simulator = Simulator(
    items=items,
    examinees=theta_values,  # True thetas
    initializer=...,
    selector=...,
    estimator=...,
    stopper=...
)
simulator.simulate()

# Extract results
for i, examinee in enumerate(theta_values):
    theta_est = simulator.estimations[i]
    items_administered = simulator.administered_items[i]
```

**Note**: Exact API may vary; implementation should handle gracefully if catsim structure differs.

## Success Metrics (Post-Implementation)

After implementation, validation is successful if:

1. **Internal engine performance**:
   - ✓ ≥90% convergence to SE < 0.30
   - ✓ Mean test length 8-12 items
   - ✓ RMSE < 0.40
   - ✓ |Mean bias| < 0.05

2. **Comparison to catsim**:
   - ✓ Mean items within ±10%
   - ✓ RMSE within ±0.05
   - ✓ No systematic bias differences

3. **Quintile consistency**:
   - ✓ All quintiles meet convergence threshold
   - ✓ No systematic failures at ability extremes

4. **Code quality**:
   - ✓ Test coverage ≥80%
   - ✓ Type hints throughout
   - ✓ Docstrings for all public functions
