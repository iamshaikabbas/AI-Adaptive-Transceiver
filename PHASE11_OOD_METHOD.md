# PHASE 11 OOD METHOD

## Coverage / Out-of-Distribution Detection

### Classification Levels

| Level | Meaning |
|-------|---------|
| **EXACT** | Exact validated operating point exists in dataset |
| **COVERED** | Inside observed feature envelope, dense neighborhood (distance < 75th percentile of dataset NN distances) |
| **NEAR_BOUNDARY** | Inside broad feature ranges but sparse neighborhood or elevated distance |
| **OOD** | Outside validated/model-supported region |

### Method

#### 1. Exact Match Check
Search 584 operating points by (environment, speed_kmph, snr_db, channel_profile, modulation).
If found → EXACT.

#### 2. Categorical Validity
If environment, channel_profile, or modulation is not in the dataset vocabulary → OOD.

#### 3. Numerical Range Check (Extended)
Compute Doppler from speed_kmph. Check against dataset ranges with 20% margin:
- speed: [min × 0.8, max × 1.2]
- snr: [min − 2, max + 2]
- doppler: [0, max × 1.2]

If outside → OOD.

#### 4. Neighborhood Density
Find 5 nearest neighbors within same categorical group (same environment, channel, modulation).
Compute normalized distance using:

```
normalized_distance = (speed_dist + snr_dist + doppler_dist) / 3
```

where each component is:
```
feature_dist = abs(query - value) / feature_range
```

#### 5. Empirical Percentile Thresholds
From the dataset itself, compute the distribution of nearest-neighbor distances across all 584 operating points.

| Percentile | Meaning | Typical threshold |
|-----------|---------|-------------------|
| 25th | Dense neighborhood | ~0.003 |
| 75th | Moderate density | ~0.012 |
| 95th | Sparse boundary | ~0.025 |

These are derived from the actual dataset, not arbitrary constants.

### Coverage Assignment

```
if exact_match:              → EXACT
if categorical invalid:      → OOD
if numerical outside range:  → OOD
if no neighbors:             → NEAR_BOUNDARY
if nn_distance <= p75:       → COVERED
if nn_distance <= p95:       → NEAR_BOUNDARY
else:                        → NEAR_BOUNDARY
```

### Design Rationale

- **Multidimensional**: Not a simplistic range check per feature
- **Empirical thresholds**: Derived from the dataset's own distance distribution
- **Categorical-first**: Valid combinations must exist in the training data
- **Conservative**: NEAR_BOUNDARY when uncertain, rather than false COVERED
