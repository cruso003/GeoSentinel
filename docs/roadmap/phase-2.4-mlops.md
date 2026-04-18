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
- [x] Tagged model promotion (`candidate` → `staging` → `production` →
      `archived`) via `ModelVersion` registry (`backend/app/models/`
      `model_version.py`, migration `0007_model_registry`). Admin-only
      `/api/v1/models/{name}/versions` + `/promote` endpoints run the
      gate and rotate production atomically; `ai/promote.py` CLI wraps
      the two calls for the trainer.

### Evaluation harness
- [x] `backend/app/services/evaluation.py` — stdlib ROC-AUC
      (Mann-Whitney-U with tie handling), PR-AUC (trapezoidal on
      descending-score), Brier, calibration gap, and
      `evaluate_with_slices(slices=…)` for per-node / per-parameter fairness
      reports. Degenerate slices return `None` rather than raising.
- [ ] Fixed evaluation split with the last 4 weeks held out (needs real
      label data).
- [x] Evaluation gates implemented in `app/services/model_registry.py`
      `evaluate_gate()`: candidate must not regress ROC-AUC
      (`MIN_AUC_IMPROVEMENT=0.0`), not regress PR-AUC by more than 2 %
      (`MAX_PR_AUC_REGRESSION`), and not regress any per-slice AUC by
      more than 2 % (`MAX_SLICE_AUC_REGRESSION`). Rejected attempts are
      still audited so bypass attempts are visible; `force=True` writes
      a distinct `promote_model_forced` entry. Held-out split with real
      labels is still pending data access.

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
- [x] Weekly Celery task `app.tasks.retrain.sweep_retrain` (Sunday 04:00
      UTC, `ml` queue) shells out to `ai/enviroguard/train.py` +
      `ai/slopewatch/train.py`. Gated on `enable_retrain_loop` so the
      default backend image doesn't need TensorFlow — only the dedicated
      trainer image flips it on.
- [x] `ai/promote.py` CLI reads `run.json` from the training job,
      registers the candidate (`POST /models/{name}/versions`), and asks
      the API to promote it (`POST /…/promote`). The promote endpoint
      runs `evaluate_gate` and only rotates production when gates pass.
- [x] Every promotion attempt — accepted, rejected, or forced — lands in
      the hash-chain audit log (`promote_model`, `promote_model_rejected`,
      `promote_model_forced`). Retrain task itself emits
      `retrain_succeeded` / `retrain_failed` with the trainer stdout/err
      trailer.

### Acceptance

- [ ] At least one model trained on ≥ 1 month of real InfluxDB data with
      metrics logged in MLflow.
- [ ] Factor decomposition in UI is SHAP-backed.
- [ ] Drift alert has fired at least once in staging and was investigated.
