# Phase 2.4 — MLOps

Goal: move EnviroGuard and SlopeWatch from synthetic-labeled prototypes to
tracked, evaluated, drift-monitored production models.

## Checklist

### Label layer
- [x] `training_labels` table + Alembic `0006` + admin CRUD + CSV importer
      with per-row error reporting (`backend/app/api/v1/training_labels.py`,
      `backend/app/models/training_label.py`, migration
      `0006_training_labels`). `source ∈ {field, ifc_report, insar,
      synthetic}` so the evaluator can restrict to real labels.
- [ ] Ingest historical IFC incident reports and field observations from
      Tokadeh into the table (depends on data access).
- [ ] Replace synthetic labels in `ai/enviroguard/data/export.py` with real
      labels where available; keep synthetic only as augmentation flagged in
      metadata.
- [ ] For SlopeWatch, cross-check Bishop-FoS labels against any known slope
      events at Tokadeh and other reference mines (AngloGold, Rio Tinto
      publications).

### Experiment tracking
- [x] MLflow server in `docker-compose.staging.yml` (Postgres backend,
      MinIO S3 artifact store, bootstrap container that creates the
      `mlflow` bucket). `docs/ops/mlflow-staging.md` walks through the
      whole setup.
- [x] `train.py` (both EnviroGuard + SlopeWatch) logs params,
      per-epoch metrics via a keras callback, `best_val_auc/loss`, and
      uploads `.tflite` + `scaler.json` + `metadata.json` as artifacts.
      A `data_sha256` param pins every run to its exact training inputs.
- [x] `ai/_mlflow.py` no-op shim: when `MLFLOW_TRACKING_URI` is unset
      (laptop / CI), training still runs and writes a local `run.json`
      manifest next to the artifacts.
- [ ] Tagged model promotion (`Staging` → `Production`) — needs the
      retraining loop below to be in place first.

### Evaluation harness
- [x] `backend/app/services/evaluation.py` — stdlib ROC-AUC
      (Mann-Whitney-U with tie handling), PR-AUC (trapezoidal on
      descending-score), Brier, calibration gap, and
      `evaluate_with_slices(slices=…)` for per-node / per-parameter fairness
      reports. Degenerate slices return `None` rather than raising.
- [ ] Fixed evaluation split with the last 4 weeks held out (needs real
      label data).
- [ ] Evaluation gates: new model must beat current in prod on both AUCs and
      not regress > 2 % on any per-node slice (needs retraining loop).

### Explanations
- [ ] SHAP values for EnviroGuard (TreeExplainer won't apply — use
      DeepExplainer on sampled batches).
- [ ] Attention-weight export for SlopeWatch PINN.
- [ ] Replace arithmetic factor decomposition with SHAP-normalised weights
      so the `pore / tilt / insar / rainfall` breakdown becomes honest.

### Model signing + artifact integrity
- [x] Ed25519 detached signatures on `.tflite` artifacts
      (`<name>.tflite.sig`, 64 raw bytes). `tflite_runtime._verify_signature`
      checks every load.
- [x] Reject unsigned / mis-signed models when `ENV=production` or
      `model_signing_required=true`. The prod-config validator now fails
      boot without `model_signing_pubkey`.
- [ ] Extend signing to `scaler.json` + `metadata.json` (single manifest
      signature) once the training pipeline emits them together.

### Drift monitoring
- [x] PSI (Population Stability Index) with reference-quantile binning and
      `_EPS` smoothing (`backend/app/services/drift.py`).
- [x] Daily Celery task `app.tasks.drift.sweep_model_drift` (02:30 UTC)
      compares 24 h current vs 7-day reference window on both EnviroGuard
      and SlopeWatch outputs.
- [x] Prometheus gauge `gs_model_psi{model,feature}` — alert > 0.2 per
      the roadmap threshold. Grafana dashboard is a follow-up.
- [x] Per-prediction confidence histogram
      `gs_model_confidence{model}` (custom buckets 0.1…1.0) to catch the
      "everything is 0.5 now" failure mode.

### Retraining loop
- [ ] Weekly Celery task (gated) retrains on the latest window.
- [ ] Runs `ai/evaluate.py`; auto-promotes only if gates pass.
- [ ] Audit log entry for every promotion.

### Acceptance

- [ ] At least one model trained on ≥ 1 month of real InfluxDB data with
      metrics logged in MLflow.
- [ ] Factor decomposition in UI is SHAP-backed.
- [ ] Drift alert has fired at least once in staging and was investigated.
