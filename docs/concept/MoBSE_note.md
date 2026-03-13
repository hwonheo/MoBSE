# 🧠 Efficient AI Architecture via Mixture of Brain-State Experts (MoBSE)

## Concept Summary & PoC Guide

---

## Document Status (2026-03-13)

This note contains both:
- concept-level framing (what MoBSE aims to do),
- and PoC-updated implementation context (what was actually tested in v1).

Companion records:
- experiment log: [`experiments_note_2026-03-13.md`](../experiments/experiments_note_2026-03-13.md)
- summarized changes: [`CHANGELOG.md`](../CHANGELOG.md)

---

# Part 1. Concept Summary Note

## 1. Research Motivation

Recent progress in artificial intelligence—especially large transformer-based models—has been driven primarily by **scaling laws**. Increasing parameter counts and model sizes has consistently improved performance across many tasks.

However, this paradigm introduces substantial computational costs. Dense attention mechanisms require all tokens to communicate with each other, leading to quadratic complexity:

~~~text
Dense Attention Complexity
O(N²)
~~~

As models scale, this results in:

- high computational cost
- large memory requirements
- high energy consumption
- slow inference

In contrast, the **human brain performs complex cognitive computation using approximately 20 watts of power**.

One key explanation for this efficiency lies in **dynamic network reconfiguration**.

Rather than activating all neural circuits simultaneously, the brain dynamically transitions between different network states depending on task demands.

~~~text
Stimulus / Task
      ↓
Network Reconfiguration
      ↓
Task-specific Subnetwork Activation
~~~

This phenomenon has been repeatedly observed in **dynamic functional connectivity (dFC)** studies using fMRI.

Key findings include:

- brain networks switch between multiple connectivity states
- cognitive tasks increase network integration
- resting states favor modular organization

Relevant studies include:

- Allen et al. (2014)
- Shine et al. (2016)
- Bassett & Bullmore (2006)

These observations suggest that biological cognition relies not on brute-force computation but on **efficient routing of information through dynamically selected subnetworks**.

---

## 2. Core Idea

This work proposes a new architecture:

**Mixture of Brain-State Experts (MoBSE)**

The key idea is to use **brain connectivity states as routing templates for AI computation**.

Traditional AI models:

~~~text
Learn connectivity weights from scratch
~~~

MoBSE:

~~~text
Select connectivity templates derived from brain network states
~~~

Conceptually:

~~~text
Brain state
    ↓
Routing template
    ↓
Sparse computation
~~~

---

## 3. Architecture Concept

MoBSE extends the **Mixture of Experts (MoE)** framework.

Traditional MoE:

~~~text
Input
  ↓
Gating Network
  ↓
Expert Networks
  ↓
Output
~~~

MoBSE:

~~~text
Input
  ↓
Gating Network
  ↓
Brain-State Template Selection
  ↓
Sparse Graph Computation
  ↓
Output
~~~

Key difference:

~~~text
Expert = connectivity graph
~~~

Examples of possible brain-state experts:

~~~text
Expert 1 : Resting-state network
Expert 2 : Working memory network
Expert 3 : Motor network
Expert 4 : Attention network
~~~

Each expert corresponds to a **connectivity template derived from fMRI data**.

---

## 4. Key Advantages

### 4.1 Computational Efficiency

Dense attention requires:

~~~text
O(N²)
~~~

Sparse graph computation requires:

~~~text
O(E)
~~~

Where:

~~~text
E << N²
~~~

Thus, MoBSE can significantly reduce FLOPs.

---

### 4.2 Biological Plausibility

Many AI architectures lack biological grounding.

MoBSE incorporates principles observed in neuroscience:

- dynamic network reconfiguration
- modular brain organization
- task-driven network activation

---

### 4.3 Explainability

Traditional MoE models contain experts without clear interpretation.

MoBSE provides interpretable expert semantics:

~~~text
Expert activation
→ cognitive state selection
~~~

Example:

~~~text
Working memory template
→ reasoning task
~~~

This supports **explainable AI (XAI)**.

---

## 5. Important Conceptual Clarification

A critical distinction must be made regarding fMRI connectivity.

Functional connectivity represents **statistical correlation**, not causal neural pathways.

~~~text
Functional Connectivity
≠
Causal Connectivity
~~~

Therefore, MoBSE should be framed as:

~~~text
Brain connectivity patterns
→ statistical priors for routing
~~~

Rather than:

~~~text
Exact simulation of neural communication
~~~

This clarification is important for reviewer acceptance.

---

# Part 2. PoC Experiment Guide

## 1. Data Sources

Target dataset for full-scale study remains the **Human Connectome Project (HCP)**.

Dataset:

~~~text
WU-Minn HCP 1200 Subjects
~~~

Data types:

~~~text
rfMRI  (resting-state)
tfMRI  (task-based)
~~~

Access:

~~~text
https://db.humanconnectome.org
~~~

### Current PoC v1 Dataset (Implemented)

For reproducible public experiments in this repository, PoC v1 used:

~~~text
OpenNeuro ds000030 (HC-filtered subset)
~~~

with filtering:

~~~text
diagnosis = CONTROL
age >= 18
task = rest
~~~

Rationale:
- HCP direct access is handled as a separate stage.
- Public OpenNeuro route enabled immediate end-to-end validation.

### Quick Prototyping Option

For early experimentation, use the Python library:

~~~text
nilearn
~~~

Example:

~~~python
from nilearn.datasets import fetch_development_fmri
~~~

---

## 2. Brain Graph Template Construction

### Step 1 — Brain Parcellation

Use a brain atlas to reduce dimensionality.

Recommended:

~~~text
Schaefer Atlas
~~~

Suggested node count:

~~~text
100–200 nodes
~~~

Each node represents an ROI (region of interest).

PoC v1 comparison was executed for:
- 100-node
- 200-node

---

### Step 2 — Functional Connectivity

Compute connectivity matrices using ROI time series.

Method:

~~~text
Pearson Correlation
~~~

Result:

~~~text
100 × 100 connectivity matrix
~~~

Task states may include:

~~~text
Rest
Working Memory
Motor
Language
Attention
~~~

In PoC implementation, these states are represented as OS-state labels:
- `rest`, `wm`, `motor`, `language`, `attention`

---

### Step 3 — Graph Sparsification

Convert dense connectivity matrices into sparse graphs.

Recommended approach:

~~~text
Proportional thresholding
~~~

Example:

~~~text
Keep top 20% edges
~~~

Result:

~~~text
Sparse connectivity templates
~~~

These templates become **brain-state experts**.

PoC default:
- sparsity = 20%
- threshold mode = proportional

---

## 3. Toy Model Architecture

Initial PoC model:

~~~text
Input sequence
     ↓
Linear embedding
     ↓
Gating network
     ↓
Brain-state template selection
     ↓
Graph message passing
     ↓
Readout layer
~~~

Message passing can be implemented using a **Graph Neural Network (GNN) layer**.

---

## 4. Benchmark Tasks

Implemented dual-task setting:

~~~text
Task A: OS-state classification (fMRI-derived windows)
Task B: ETTh1 forecasting
~~~

Additional synthetic/public-proxy modes are retained for smoke tests.

---

## 5. Evaluation Metrics

Task metrics:

~~~text
Classification: Accuracy, F1-macro
Forecasting: MAE, MSE
~~~

Efficiency metrics:

~~~text
FLOPs
Memory usage
Inference latency
~~~

Baselines:

~~~text
Transformer
Sparse Transformer
Mixture of Experts
~~~

---

## 6. Expected Outcomes

PoC objectives:

~~~text
1. Verify training convergence
2. Validate routing stability
3. Measure FLOPs reduction
~~~

Expected results:

~~~text
Comparable prediction accuracy
Lower computational cost
~~~

### PoC v1 Snapshot (HC127, balanced 3-seed)

Observed summary:
- 100-node gave better classification means.
- 200-node showed slightly better ETTh1 MSE mean, but larger variance.

Representative means (3 seeds):

~~~text
100-node: Accuracy 0.1469, F1 0.1141, MAE 2.2257, MSE 8.8458
200-node: Accuracy 0.1099, F1 0.0949, MAE 2.2380, MSE 8.7316
~~~

Interpretation:
- For this PoC stage, 100-node is more stable for classification.
- 200-node requires further data-quality control and/or scaling to justify added cost.

---

## 7. Practical Clarifications from v1

### 7.1 Naming / Scope

Repository terminology now uses:

~~~text
OS (open-source proxy) task
~~~

instead of direct `HCP` naming in runtime interfaces, to avoid overclaiming data provenance.

### 7.2 Nuisance Regression in Current Pipeline

Implemented denoising stack (default):

~~~text
CompCor-like confounds
+ GSR
+ derivative/quadratic confound expansion
+ detrend + 0.008-0.1 Hz filtering
~~~

Important limitation:
- raw `ds000030` snapshot used here does not provide full fMRIPrep confounds TSV for strict 24P/36P reproduction.
- therefore current approach is a principled approximation, not an exact replica of every published denoising preset.

### 7.3 Why Keep "HCP-Style" Classification Framing?

Even when PoC v1 used an open public proxy dataset (`ds000030`), the task framing is intentionally kept aligned with HCP-style state classification because:

- it tests whether routing can separate brain-state-like conditions under a controlled label space,
- it provides a direct bridge to the planned full-scale HCP stage without changing the core objective,
- and it lets us validate model behavior (routing stability, efficiency tradeoff) before restricted-data expansion.

In short, PoC v1 validates the *method* under public constraints; HCP remains the target dataset for the main claim stage.

---

# Part 3. Core References

## Brain Network Science

Allen, E. A. et al. (2014)  
*Tracking whole-brain connectivity dynamics in the resting state*  
*Cerebral Cortex*

Bassett, D. S., & Bullmore, E. (2006)  
*Small-world brain networks*  
*The Neuroscientist*

Bullmore, E., & Sporns, O. (2009)  
*Complex brain networks*  
*Nature Reviews Neuroscience*

---

## Neural Oscillations

Buzsáki, G., & Draguhn, A. (2004)  
*Neuronal oscillations in cortical networks*  
*Science*

Canolty, R., & Knight, R. (2010)  
*Cross-frequency coupling*  
*Trends in Cognitive Sciences*

Fries, P. (2005)  
*Communication through neuronal coherence*  
*Trends in Cognitive Sciences*

---

## Dynamic Brain Networks

Shine, J. M. et al. (2016)  
*The dynamics of functional brain networks during cognitive task performance*  
*Neuron*

Calhoun, V. D. et al. (2014)  
*The chronnectome: time-varying connectivity networks*  
*Neuron*

---

## Sparse AI Architectures

Fedus, W. et al. (2022)  
*Switch Transformers*  
*Journal of Machine Learning Research*

Maass, W. et al. (2002)  
*Real-time computing without stable states*  
*Neural Computation*

---

## fMRI Denoising / Regression Practice

Wang, C. Y. et al. (2024)  
*Choosing denoising techniques for your fMRI data*  
*PLOS Computational Biology*

AJNR Resting-State fMRI Review (2024)  
*State of the art and practical recommendations*  
*American Journal of Neuroradiology*

XCP-D documentation (living reference)  
*Confound-based regression presets (24P/27P/36P, acompcor variants)*  
*PennLINC / XCP-D Docs*

---

# Part 4. Future Research Directions

## 1. Learnable Brain Templates

Instead of fixed templates:

~~~text
Brain template
+
Trainable perturbation
~~~

---

## 2. Graph Mixture Model

~~~text
Mixture of Brain-State Graphs
~~~

---

## 3. Oscillatory Graph Dynamics

Node states represented by:

~~~text
Phase
Frequency
~~~

This enables oscillatory network computation.

---

# Final Summary

MoBSE combines three major ideas:

~~~text
Dynamic brain states
+
Sparse routing
+
Graph computation
~~~

Core concept:

~~~text
Brain state
→ routing template
~~~

This architecture aims to provide:

- improved computational efficiency
- biological plausibility
- interpretable model behavior

MoBSE therefore represents a promising direction for **brain-inspired AI architecture design**.
