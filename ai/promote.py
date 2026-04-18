"""Register + promote a trained artifact (Phase 2.4 §5).

Usage:

  # Register a candidate from a just-trained directory (reads run.json).
  python -m ai.promote register \
      --artifacts ai/enviroguard/artifacts \
      --api http://localhost:8000/api/v1 \
      --token "$GS_ADMIN_TOKEN"

  # Ask the backend to run the gate and promote if it passes.
  python -m ai.promote promote \
      --name enviroguard \
      --version-id <uuid-from-register-response> \
      --api http://localhost:8000/api/v1 \
      --token "$GS_ADMIN_TOKEN"

The CLI stays *thin* on purpose: the gate logic, audit entry, and
production rotation all live in the backend service so the same rules
apply whether a promotion comes from CI, a notebook, or curl.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - trusted
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} -> {e.code}: {body_text}") from None


def _cmd_register(args: argparse.Namespace) -> int:
    manifest_path = Path(args.artifacts) / "run.json"
    if not manifest_path.exists():
        raise SystemExit(f"{manifest_path} not found — run training first.")
    manifest = json.loads(manifest_path.read_text())

    name = manifest.get("model")
    if name not in ("enviroguard", "slopewatch"):
        raise SystemExit(f"Unexpected model name in manifest: {name!r}")

    # Metrics: keep the full manifest's numeric fields so the gate sees
    # everything (roc_auc, pr_auc, slice AUCs if present). Downstream the
    # backend only pays attention to the keys it recognises.
    metrics = {
        k: v
        for k, v in manifest.items()
        if isinstance(v, (int, float, dict))
        and k not in {"created_at", "run_name"}
    }
    body = {
        "name": name,
        "version": manifest.get("run_name") or manifest.get("created_at") or "unknown",
        "metrics": metrics,
        "data_sha256": manifest.get("data_sha256"),
        "artifact_uri": str(Path(args.artifacts).resolve()),
        "mlflow_run_id": manifest.get("mlflow_run_id"),
    }
    resp = _request(
        "POST", f"{args.api}/models/{name}/versions", args.token, body
    )
    print(json.dumps(resp, indent=2))
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    body = {"force": args.force}
    resp = _request(
        "POST",
        f"{args.api}/models/{args.name}/versions/{args.version_id}/promote",
        args.token,
        body,
    )
    print(json.dumps(resp, indent=2))
    return 0 if resp.get("promoted") else 1


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser("ai.promote")
    p.add_argument("--api", default="http://localhost:8000/api/v1")
    p.add_argument("--token", required=True, help="Bearer token for an esg_admin")
    sub = p.add_subparsers(dest="cmd", required=True)

    reg = sub.add_parser("register")
    reg.add_argument("--artifacts", required=True)
    reg.set_defaults(func=_cmd_register)

    prom = sub.add_parser("promote")
    prom.add_argument("--name", required=True)
    prom.add_argument("--version-id", required=True)
    prom.add_argument("--force", action="store_true")
    prom.set_defaults(func=_cmd_promote)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
