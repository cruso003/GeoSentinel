# EnviroGuard — model stack and training

GeoSentinel's environmental-breach forecaster. Phase-1 ships a trained
baseline that is loaded and served by the backend; Phase-2 (pre-incubation)
upgrades the baseline to the LSTM+Attention architecture already
specified in `model.py`, trained on real sensor data.

## Current inference stack

The backend service `app/services/enviroguard.py` tries each path in
order and takes the first one that produces a prediction:

1. **LSTM+Attention TFLite artifact** — the Phase-2 target. Not shipped
   in-tree today. Will land under
   `$GEOSENTINEL_MODEL_DIR/enviroguard/artifacts/enviroguard.tflite`
   once trained on real data.
2. **ONNX GBM baseline** — shipped in `artifacts/`. Seven
   `GradientBoostingClassifier` heads (one per IFC exceedance target),
   trained on scenario-overlaid synthetic Tokadeh data, exported to
   ONNX, served via `app/services/onnx_runtime.py`.
3. **Deterministic surrogate** — hour-of-day sine drift. Gated behind
   `settings.enable_synthetic_ai_fallback`; prod validator forbids it.

The baseline is the first path that produces a *real trained model's
prediction*; the service previously fell straight from (1) to (3) and
served `sin(hour_of_day)` as if it were inference.

## Baseline training

```
python -m ai.enviroguard.train_baseline --days 180
```

Writes seven ONNX files + `metadata.json` + `run_manifest.json` to
`ai/enviroguard/artifacts/`.

### Data

- **Source today:** `ai/enviroguard/data/export.py:_synthetic_frame` —
  a deterministic Tokadeh frame covering wet / dry seasons, diurnal
  pH / DO / PM2.5 drift, and random storm events, plus
  **scenario-overlaid exceedance events** (pH acidic spills, turbidity
  storm residues, DO drops, conductivity spikes, PM2.5 dust events) so
  every IFC head has positive examples in the training frame.
- **Volume:** 180 days × 3 nodes × 15-min resolution = 51 840 raw rows
  → 12 672 sliding 96 h windows (stride = 1 h).
- **Labels:** `_label()` emits binary targets for every IFC parameter
  at 24 h and 72 h horizons — the model is "will any 15-min reading
  breach the IFC threshold in the next N hours."
- **Split:** chronological 75 / 25 train / val. No window straddles the
  split, so val-set metrics are honest wrt leakage.

Pre-incubation swaps `_synthetic_frame` for real sources. Candidates
researched for the proposal:

- **OpenAQ** (Monrovia PM2.5, if coverage exists — API v3,
  `countries_id=LR`).
- **US-EPA DataShed** acid-mine-drainage CSVs (CC-BY-NC-SA; pH,
  conductivity, metals; passive-treatment sites in Pennsylvania — not
  mining-industry *scale* but useful calibration).
- **IEEE DataPort "IoT water quality"** (temperature, conductivity, TDS
  with spike-contamination scenarios).
- **QUADICA v2** (German catchment-scale water quality time series).
- **Operator-provided** historical water-quality / air-quality logs
  from one of ArcelorMittal Liberia (Nimba), HPX / SMFG (Nimba), Bea
  Mountain (Cape Mount) — the strongest ask if a pre-incubation
  conversation lands.

Swapping is one flag: `python -m ai.enviroguard.train_baseline
--parquet data/real.parquet`.

### Features

Per window (`features.py`):

- For each of the 15 sequence features: `mean`, `std`, `min`, `max`,
  `last`, `slope_per_hour`.
- Plus five window-end globals: `hour_sin`, `hour_cos`,
  `wet_season_flag`, `rainfall_mm_24h`, `rainfall_mm_1h`.

Total: `15 × 6 + 5 = 95` features per window.

The feature list is baked into `metadata.json` so the runtime and the
training script can't drift silently.

### Models

Seven independent `GradientBoostingClassifier` instances
(`n_estimators=150`, `max_depth=3`, `learning_rate=0.05`,
`subsample=0.9`), one per IFC head, exported to a separate ONNX file.
A head with a degenerate single-class training window falls back to a
constant-probability `LogisticRegression` stub so the ONNX graph is
still a valid classifier.

### Honest performance

The baseline's held-out holdout metrics on the current synthetic frame:

| Head | ROC-AUC | PR-AUC | Pos-rate (val) |
|---|---|---|---|
| ph_24h | 0.55 | 0.28 | 0.10 |
| turbidity_24h | 0.61 | 0.62 | 0.52 |
| dissolved_oxygen_24h | 0.55 | 0.24 | 0.09 |
| conductivity_24h | 0.66 | 0.34 | 0.12 |
| pm25_24h | 0.53 | 0.11 | 0.07 |
| ph_72h | 0.50 | 0.23 | 0.23 |
| turbidity_72h | 0.65 | 0.94 | 0.89 |

Pre-incubation delivery is a trained model with ROC-AUC ≥ 0.80 on real
operator water-quality data.

**Reading these numbers.** The baseline is a *pipeline proof*, not an
operational predictor. The scenario-overlaid synthetic frame produces
events whose onset is intentionally random, which caps the upper bound
on forward-horizon prediction accuracy; current-state features (last
value, last-24 h slope) carry whatever signal the classifier learns.
The purpose of shipping the baseline is to replace the
`sin(hour_of_day)` surrogate with an inference path that genuinely
produces model probabilities, so the integration surface — ONNX
loading, feature extraction, service wiring, metadata contract — is
exercised end-to-end today. Real-data retraining in pre-incubation is
what moves the accuracy bar.

## Phase-2 LSTM upgrade (pre-incubation)

The LSTM+Attention architecture in `model.py` is the training target
once real labelled data is available. `train.py` already implements
the TensorFlow training loop with MLflow tracking, scaler export,
TFLite conversion, and the Ed25519-signed artifact handoff to
`app/services/tflite_runtime.py`. Delivery steps:

1. Export operator or OpenAQ time series to the training parquet
   schema (`ai/enviroguard/data/export.py` is the reference).
2. `python -m ai.enviroguard.train --data real.parquet --epochs 40`.
3. Sign the artifact with the offline Ed25519 key the model registry
   expects (`tflite_runtime._verify_signature`).
4. Promote via the model registry — the backend picks the TFLite path
   automatically on the next inference call because it is listed first
   in `services/enviroguard.py`.

No service-side code changes.
