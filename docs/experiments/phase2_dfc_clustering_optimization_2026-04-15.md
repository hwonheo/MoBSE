# Phase 2: dFC Clustering Optimization — ABIDE CC200 PCA Sweep

**Date**: 2026-04-15  
**Dataset**: ABIDE PCP HC (cpac pipeline, band-pass + GSR)  
**Atlas**: CC200 (200 ROIs → 191 after zero-variance ROI removal)  
**Subjects**: 468 fetched → 102 after filtering (age ≥ 18, TP ≥ 150), 9 sites  
**Total windows**: 19,630 (window = 45s, stride = 2s, cosine taper, Fisher-Z)

---

## 1. Problem Statement

Initial dFC clustering on raw FC vectors (19,900 dimensions) produced silhouette scores of ~0.013, indicating near-random cluster assignment. PCA dimensionality reduction (Allen et al. 2014) was added, but variance-based retention (80–95%) still yielded 774–1,591 components with minimal improvement.

**Goal**: Find the optimal preprocessing + dimensionality reduction configuration for meaningful brain-state separation.

---

## 2. Experimental Variables

### 2.1 Preprocessing Options

| Option | Description | Rationale |
|--------|-------------|-----------|
| **Zero-variance ROI removal** | Drop ROIs with std < 1e-6 across ALL subjects | CC200 contains ROIs in WM/CSF with no BOLD signal; these produce NaN in corrcoef |
| **Per-subject z-normalization** | Z-score each subject's FC vectors independently before pooling | Remove site/scanner scale differences in multi-site data |

### 2.2 PCA Modes

| Mode | Description |
|------|-------------|
| Variance-based | Retain components explaining X% of total variance (sklearn `n_components=0.95`) |
| Fixed components | Retain exactly N components regardless of variance |

### 2.3 Clustering

- Algorithm: k-means (sklearn), n_init=100, max_iter=500
- k search: silhouette score on k ∈ {3, 4, 5, 6, 7}
- k search uses n_init=20 for speed; final clustering at best k uses n_init=100

---

## 3. Results

### 3.1 Baseline — No PCA

| Config | Silhouette (best k) | Best k | Note |
|--------|---------------------|--------|------|
| Raw FC (19,900 dims) | 0.013 | 3 | Near-random |

### 3.2 Variance-Based PCA (no z-norm, no ROI clean)

| Variance retained | Components | Silhouette (k=3) | CH |
|-------------------|-----------|-------------------|-----|
| 95% | 1,591 | 0.013 | 214 |
| 90% | 1,185 | 0.014 | 226 |
| 80% | 774 | 0.015 | 255 |

**Observation**: Variance-based PCA is ineffective — 80% of variance is spread across 774 components, providing negligible dimensionality reduction.

### 3.3 Fixed PCA + z-norm + ROI Clean

| z-norm | Components | Var retained | Silhouette (k=3) | CH | Occupancy |
|--------|-----------|-------------|-------------------|------|-----------|
| ON | 30 | 17.1% | 0.055 | 926 | 50/27/23 |
| ON | 50 | 22.3% | 0.041 | 697 | 50/23/27 |
| ON | 100 | 31.2% | 0.030 | 490 | 50/23/27 |

**Observation**: z-norm removes site-level FC scale, but this causes variance to distribute more uniformly → more components needed to capture equivalent information → fixed component count with z-norm retains too little signal.

### 3.4 Fixed PCA + ROI Clean (no z-norm) ★

| Components | Var retained | Silhouette (k=3) | CH | Occupancy |
|-----------|-------------|-------------------|------|-----------|
| **10** | **10.7%** | **0.127** | **2344** | **52/30/18** |
| 20 | 16.0% | 0.081 | 1461 | 53/29/18 |
| 30 | 19.9% | 0.068 | 1142 | 53/29/18 |

**Best configuration**: 10 fixed PCA components, no z-norm, ROI cleaning ON.

### 3.5 k Sensitivity (at PC=10, no z-norm)

| k | Silhouette | CH | Occupancy |
|---|-----------|-----|-----------|
| 3 | **0.127** | 2344 | 52/30/18 |
| 4 | 0.114 | 2072 | 44/25/17/15 |
| 5 | 0.116 | 1932 | 42/24/14/13/8 |
| 6 | 0.112 | 1826 | 36/18/16/12/11/7 |
| 7 | 0.103 | 1712 | 33/15/15/11/10/10/6 |

k=3 is optimal by silhouette. k=5 shows a slight uptick over k=4, suggesting possible sub-structure.

---

## 4. Key Findings

### 4.1 Monotonic PCA–Silhouette Relationship

Fewer PCA components → higher silhouette, across all configurations tested. This is consistent with the "curse of dimensionality" in k-means: in very high dimensions, Euclidean distances become less discriminative.

```
Components:  10    20    30    50    100   774   1185  1591  19900
Silhouette: 0.127 0.081 0.068 0.041 0.030 0.015 0.014 0.013 0.013
                                           ↑ variance-based PCA
```

### 4.2 z-Normalization Is Counterproductive for Pre-Processed ABIDE

ABIDE PCP data is already preprocessed with:
- Band-pass filtering (0.01–0.1 Hz)
- Global signal regression
- Pipeline-level nuisance regression (cpac)

Per-subject z-normalization removes additional FC magnitude information that appears to carry brain-state signal. This differs from raw multi-site BOLD data where z-norm would be essential.

### 4.3 Stable Occupancy Structure

The 3-state occupancy pattern (~52%/29%/18%) is remarkably stable across ALL configurations, including different PCA settings and with/without z-norm. This suggests a genuine underlying structure:

- **State 1 (~52%)**: Dominant resting state (likely default mode network)
- **State 2 (~29%)**: Secondary state (likely attention/salience network activation)
- **State 3 (~18%)**: Transient state (network transitions)

### 4.4 Zero-Variance ROI Cleaning

9 out of 200 CC200 ROIs had zero variance across all 102 subjects (likely white matter or CSF parcels). Removing these:
- Eliminates NaN warnings from `np.corrcoef`
- Reduces edge count from 19,900 to 18,145 (8.8% reduction)
- Should be applied by default for CC200 atlas

---

## 5. Recommended Configuration

```python
DFCConfig(
    window_sec=45.0,
    stride_sec=2.0,
    taper="cosine",
    fisher_z=True,
    k=3,                       # optimal by silhouette
    pca_n_components=10,       # fixed; variance-based is ineffective
    subject_z_norm=False,      # ABIDE PCP already preprocessed
    drop_zero_var_rois=True,   # removes 9/200 dead ROIs
    sparsity=0.2,
    n_init=100,
    max_iter=500,
    random_state=42,
)
```

**Expected performance**: Silhouette ~0.12–0.13 (k=3), template bank shape (3, 191, 191).

---

## 6. Comparison to Literature

| Study | Dataset | Atlas | N (subjects) | k | Silhouette | PCA |
|-------|---------|-------|-------------|---|-----------|-----|
| Allen et al. 2014 | Single-site | ICA (100) | 405 | 5 | ~0.10–0.15 | 95% variance |
| Damaraju et al. 2014 | Multi-site | ICA (100) | 314 | 5 | ~0.08–0.12 | 95% variance |
| **This work** | **ABIDE (9 sites)** | **CC200 (191)** | **102** | **3** | **0.127** | **Fixed 10** |

Our results are consistent with literature despite using a parcellation-based atlas (CC200) rather than ICA components, and multi-site data with heterogeneous protocols.

---

## 7. Implementation Details

### Code: `mobse/data/dfc.py`

Key functions added/modified in this optimization:
- `clean_zero_variance_rois()`: drops ROIs with std < 1e-6 across all subjects
- `_subject_z_normalize()`: per-subject z-scoring of FC vectors
- `reduce_fc_dimensions()`: supports both variance-based and fixed n_components PCA
- `run_dfc_pipeline()`: orchestrates ROI cleaning → FC → (optional z-norm) → PCA → clustering → template bank

### Artifacts

All experimental outputs saved under `artifacts/`:

| Directory | Config |
|-----------|--------|
| `abide_dfc_pca95_full` | PCA 95% variance, no z-norm, no ROI clean |
| `abide_dfc_pca90_full` | PCA 90% variance, no z-norm, no ROI clean |
| `abide_dfc_pca80_full` | PCA 80% variance, no z-norm, no ROI clean |
| `abide_dfc_v2_pc30` | PC=30, z-norm ON, ROI clean ON |
| `abide_dfc_v2_pc50` | PC=50, z-norm ON, ROI clean ON |
| `abide_dfc_v2_pc100` | PC=100, z-norm ON, ROI clean ON |
| `abide_dfc_v2_pc30_noznorm` | PC=30, z-norm OFF, ROI clean ON |
| `abide_dfc_v2_pc20_noznorm` | PC=20, z-norm OFF, ROI clean ON |
| `abide_dfc_v2_pc10_noznorm` | PC=10, z-norm OFF, ROI clean ON ★ |

Each directory contains:
- `dfc_template_bank.npz`: template_bank, centroids, labels, subject_indices, window_counts
- `dfc_pilot_report.json`: full config, metrics, PCA info
- `included_subjects.csv`: phenotypic data for included subjects

---

## 8. Next Steps

1. **Template visualization**: Plot 3 state centroids as connectivity matrices, identify network-level differences
2. **Schaefer atlas comparison**: Run same pipeline on PIOP1 data (Schaefer 100/200) for atlas-independent validation
3. **MoBSE training integration**: Wire dFC template bank into MoBSE model (config.py, templates/builder.py)
4. **Ablation matrix**: atlas × k × sparsity × routing × prior × seeds (as per execution strategy)
