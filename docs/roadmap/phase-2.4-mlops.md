# Phase 2.4 — MLOps

Goal: move EnviroGuard and SlopeWatch from synthetic-labeled prototypes to
tracked, evaluated, drift-monitored production models.

## Checklist

### Label layer
- [ ] Ingest historical IFC incident reports and field observations from
      Tokadeh into `training_label(site_id, node_id, parameter, t_start,
      t_end, label, source)`.
- [ ] Replace synthetic labels in `ai/enviroguard/data/export.py` with real
      labels where available; keep synthetic only as augmentation flagged in
      metadata.
- [ ] For SlopeWatch, cross-check Bishop-FoS labels against any known slope
      events at Tokadeh and other reference mines (AngloGold, Rio Tinto
      publications).

### Experiment tracking
- [ ] MLflow server in `docker-compose.staging.yml`.
- [ ] `train.py` logs params, metrics, artifacts, and the data checksum.
- [ ] Tagged model promotion (`Staging` → `Production`).

### Evaluation harness
- [ ] `ai/evaluate.py` with ROC-AUC, PR-AUC, calibration (Brier), per-node
      fairness, false-positive rate at fixed recall.
- [ ] Fixed evaluation split with the last 4 weeks held out.
- [ ] Evaluation gates: new model must beat current in prod on both AUCs and
      not regress > 2 % on any per-node slice.

### Explanations
- [ ] SHAP values for EnviroGuard (TreeExplainer won't apply — use
      DeepExplainer on sampled batches).
- [ ] Attention-weight export for SlopeWatch PINN.
- [ ] Replace arithmetic factor decomposition with SHAP-normalised weights
      so the `pore / tilt / insar / rainfall` breakdown becomes honest.

### Model signing + artifact integrity
- [ ] Sign `.tflite` + `scaler.json` + `metadata.json` with a long-lived
      offline key.
- [ ] `tflite_runtime.load` verifies signature before loading.
- [ ] Reject unsigned models in `ENV=production`.

### Drift monitoring
- [ ] Daily Celery task computes PSI (population stability index) per
      feature against the training distribution.
- [ ] Prometheus gauge `gs_model_psi{model,feature}`; Grafana alert > 0.2.
- [ ] Per-prediction confidence histogram.

### Retraining loop
- [ ] Weekly Celery task (gated) retrains on the latest window.
- [ ] Runs `ai/evaluate.py`; auto-promotes only if gates pass.
- [ ] Audit log entry for every promotion.

### Acceptance

- [ ] At least one model trained on ≥ 1 month of real InfluxDB data with
      metrics logged in MLflow.
- [ ] Factor decomposition in UI is SHAP-backed.
- [ ] Drift alert has fired at least once in staging and was investigated.
