# MLflow staging setup

Phase 2.4 scaffolds experiment tracking so every EnviroGuard / SlopeWatch
run is reproducible: the code state (git SHA), the data (SHA-256 of the
input Parquet), the params, the metrics, and the artifacts all land in
one place.

## What's in the stack

`docker-compose.staging.yml` is an overlay on top of the dev compose
file. It adds:

- **MinIO** — S3-compatible artifact store, seeded with a `mlflow`
  bucket via a one-shot `minio-bootstrap` container.
- **MLflow server** (`ghcr.io/mlflow/mlflow:v2.18.0`) — backend store on
  the existing Postgres (`mlflow` schema is created on first boot),
  artifact root at `s3://mlflow/`.
- `MLFLOW_TRACKING_URI=http://mlflow:5000` injected into `backend` and
  `celery-worker` so future online-learning jobs log to the same server.

## Run it

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.staging.yml up --build
```

- MLflow UI → http://localhost:5000
- MinIO console → http://localhost:9001 (user `mlflow` / pass
  `mlflow-staging-secret`)

Rotate those credentials before anything more than a local demo:
`MINIO_ROOT_PASSWORD`, `AWS_SECRET_ACCESS_KEY`, plus a real Postgres
password.

## Train a model against it

From a host shell (not inside the container), point the training
scripts at the MLflow server:

```bash
export MLFLOW_TRACKING_URI=http://localhost:5000
export MLFLOW_S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=mlflow
export AWS_SECRET_ACCESS_KEY=mlflow-staging-secret

python -m ai.enviroguard.train \
    --data ai/enviroguard/data/enviroguard.parquet \
    --epochs 40 \
    --run-name "enviroguard-tokadeh-$(date -u +%Y%m%d)"

python -m ai.slopewatch.train --epochs 60  # no --data → synthetic FoS labels
```

Each run records:

- `data_sha256` — rerun integrity check. If two runs claim the same
  model version but different checksums, something is wrong upstream.
- per-epoch `loss`, `val_auc`, `val_loss`, `val_mae` (streamed via a
  keras callback so partial runs are still useful).
- `best_val_auc` / `best_val_loss` — the promotion gate reads these.
- `enviroguard.tflite` (or `slopewatch.tflite`) + `scaler.json` +
  `metadata.json` uploaded as artifacts.

A `run.json` also lands next to the local artifact directory so an
operator without MLflow access can still trace a deployed model to the
run that produced it.

## No MLflow? No problem

If `MLFLOW_TRACKING_URI` is unset the training scripts fall back to a
null tracker — artifacts still land on disk, they just aren't pushed to
a server. This keeps `python -m ai.enviroguard.train` working on a
laptop with no infra.

## Model signing handoff

`tflite_runtime._verify_signature` requires `<model>.tflite.sig` next to
the artifact in production. Sign out-of-band with the offline key:

```bash
python - <<'PY'
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

priv = Ed25519PrivateKey.from_private_bytes(
    bytes.fromhex(open("/secure/offline.key").read().strip())
)
art = Path("ai/enviroguard/artifacts/enviroguard.tflite")
(art.with_suffix(art.suffix + ".sig")).write_bytes(priv.sign(art.read_bytes()))

# Publish the matching pubkey hex as MODEL_SIGNING_PUBKEY on the backend.
pub = priv.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
).hex()
print("MODEL_SIGNING_PUBKEY =", pub)
PY
```

The signing ceremony itself — generating and storing the offline key —
should happen on an air-gapped machine; only the public key hex and the
detached signature ever touch the build pipeline.
