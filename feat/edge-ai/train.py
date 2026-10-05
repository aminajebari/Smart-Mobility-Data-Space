"""Train, evaluate, export (ONNX) and benchmark the edge congestion model.

Usage:
    python train.py                       # deterministic local fixture (default)
    python train.py --source api          # pull standardized records from the provider API (Module 2)
    python train.py --source file --input records.jsonl

The raw training data stays on this edge node (data/ is git-ignored); only the
model and its metrics are shared.
"""
import argparse
import json
import os
import pickle
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import onnxruntime as ort
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from edge_ai.features import FEATURES, HORIZON, WINDOW, build_dataset

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
MODEL_NAME = "congestion_rf"
MODEL_VERSION = "1.0.0"


# -- data -----------------------------------------------------------------------
def fixture_records(days: int, seed_offset: int = 0) -> list[dict]:
    """Local test fixture: replay Module 1's seeded traffic simulator in batch mode (simulated time)."""
    sys.path.append(os.environ.get("DATA_SIMULATION_PATH", str(ROOT.parent / "data-simulation")))
    from simulators.base_provider import CONFIG_PATH
    from simulators.traffic_sensor import TrafficSensor

    # Built without __init__ so nothing is created in Module 1's data folder (we never write to its storage).
    sensor = TrafficSensor.__new__(TrafficSensor)
    sensor.provider_id = "traffic_sensor_1"
    sensor.config = TrafficSensor._load_yaml(CONFIG_PATH)["providers"]["traffic_sensor_1"]
    sensor.rng = np.random.default_rng(1000 + seed_offset)
    sensor.state = "normal"

    ts, records = datetime(2026, 9, 1), []
    for _ in range(days * 24 * 3600 // 5):
        records.append(sensor.generate_record(ts))
        ts += timedelta(seconds=5)
    return records


def api_records(limit: int) -> list[dict]:
    import httpx
    url = os.environ.get("TRAFFIC_API_URL", "http://localhost:8001")
    response = httpx.get(f"{url}/data", params={"dataset_id": "traffic_sensor_1.traffic_flow", "limit": limit,
                                                "purpose": "congestion_prediction"},
                         headers={"X-API-Key": os.environ.get("EDGE_API_KEY", "")}, timeout=30)
    response.raise_for_status()
    return response.json()["records"]


def load_records(args) -> list[dict]:
    if args.source == "file":
        return [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line]
    if args.source == "api":
        return api_records(1000)
    cache = DATA_DIR / f"fixture_{args.days}d.jsonl"
    if cache.exists():
        return [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line]
    records = fixture_records(args.days)
    DATA_DIR.mkdir(exist_ok=True)
    cache.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return records


# -- evaluation & benchmark ---------------------------------------------------------
def metrics(y_true, y_pred, y_prob=None) -> dict:
    result = {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    if y_prob is not None:
        result["roc_auc"] = round(roc_auc_score(y_true, y_prob), 4)
    return result


def latency_ms(fn, runs: int = 500) -> dict:
    for _ in range(20):
        fn()
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return {"mean": round(statistics.mean(samples), 4), "p50": round(samples[len(samples) // 2], 4),
            "p95": round(samples[int(len(samples) * 0.95)], 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["fixture", "api", "file"], default="fixture")
    parser.add_argument("--input", help="JSONL file for --source file")
    parser.add_argument("--days", type=int, default=3, help="simulated days for the fixture")
    args = parser.parse_args()

    records = load_records(args)
    X, y = build_dataset(records)
    split = int(len(X) * 0.8)  # chronological split: test on the most recent 20 %
    X_train, X_test, y_train, y_test = X[:split], X[split:], y[:split], y[split:]
    print(f"{len(records)} records -> {len(X)} windows (train {len(X_train)}, test {len(X_test)}), "
          f"positive rate {y.mean():.1%}")

    # baselines
    incident_idx = FEATURES.index("incident")
    persistence = metrics(y_test, X_test[:, incident_idx].astype(int))
    logreg = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X_train, y_train)
    logreg_metrics = metrics(y_test, logreg.predict(X_test), logreg.predict_proba(X_test)[:, 1])

    model = RandomForestClassifier(n_estimators=60, max_depth=10, min_samples_leaf=5,
                                   class_weight="balanced", random_state=42, n_jobs=1)
    model.fit(X_train, y_train)
    rf_metrics = metrics(y_test, model.predict(X_test), model.predict_proba(X_test)[:, 1])
    print("persistence baseline:", persistence)
    print("logistic regression :", logreg_metrics)
    print("random forest       :", rf_metrics)

    # export
    MODELS_DIR.mkdir(exist_ok=True)
    pkl_path, onnx_path = MODELS_DIR / f"{MODEL_NAME}.pkl", MODELS_DIR / f"{MODEL_NAME}.onnx"
    pkl_path.write_bytes(pickle.dumps(model))
    onnx_model = convert_sklearn(model, initial_types=[("input", FloatTensorType([None, len(FEATURES)]))],
                                 options={id(model): {"zipmap": False}}, target_opset=17)
    onnx_path.write_bytes(onnx_model.SerializeToString())

    # ONNX must reproduce the original model
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    onnx_prob = session.run(None, {input_name: X_test})[1][:, 1]
    max_diff = float(np.max(np.abs(onnx_prob - model.predict_proba(X_test)[:, 1])))
    onnx_metrics = metrics(y_test, (onnx_prob >= 0.5).astype(int), onnx_prob)

    sample = X_test[:1]
    benchmark = {
        "model_size_bytes": {"sklearn_pickle": pkl_path.stat().st_size, "onnx": onnx_path.stat().st_size},
        "single_prediction_latency_ms": {
            "sklearn": latency_ms(lambda: model.predict_proba(sample)),
            "onnxruntime": latency_ms(lambda: session.run(None, {input_name: sample})),
        },
        "batch_1000_latency_ms": {
            "sklearn": latency_ms(lambda: model.predict_proba(X_test[:1000]), runs=50),
            "onnxruntime": latency_ms(lambda: session.run(None, {input_name: X_test[:1000]}), runs=50),
        },
        "onnx_max_probability_difference": max_diff,
        "hardware": "CPU, single process (" + sys.platform + ")",
    }
    print("benchmark:", json.dumps(benchmark, indent=2))

    metadata = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "task": f"binary classification: congestion (incident) within the next {HORIZON} sensor records",
        "algorithm": "RandomForestClassifier (60 trees, max depth 10)",
        "edge_format": "ONNX (opset 17)",
        "features": FEATURES,
        "window": WINDOW,
        "horizon": HORIZON,
        "threshold": 0.5,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "training_source": args.source,
        "training_records": len(records),
        "train_windows": len(X_train),
        "test_windows": len(X_test),
        "positive_rate": round(float(y.mean()), 4),
        "metrics": {"random_forest": rf_metrics, "random_forest_onnx": onnx_metrics,
                    "logistic_regression": logreg_metrics, "persistence_baseline": persistence},
        "benchmark": benchmark,
    }
    (MODELS_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "evaluation.md").write_text(render_report(metadata), encoding="utf-8")
    print(f"saved {onnx_path.name}, {pkl_path.name}, metadata.json and reports/evaluation.md")


def render_report(m: dict) -> str:
    rows = "\n".join(
        f"| {name} | {v['accuracy']:.3f} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} | "
        f"{v.get('roc_auc', float('nan')):.3f} |"
        for name, v in m["metrics"].items())
    b = m["benchmark"]
    s, o = b["single_prediction_latency_ms"]["sklearn"], b["single_prediction_latency_ms"]["onnxruntime"]
    bs, bo = b["batch_1000_latency_ms"]["sklearn"], b["batch_1000_latency_ms"]["onnxruntime"]
    size = b["model_size_bytes"]
    return f"""# Edge AI - Congestion prediction: evaluation report

Generated by `train.py` on {m['trained_at']}.

- **Task:** {m['task']}
- **Features ({len(m['features'])}):** {', '.join(m['features'])} (window of {m['window']} records)
- **Data:** {m['training_records']} records ({m['training_source']}), chronological split,
  {m['train_windows']} train / {m['test_windows']} test windows, positive rate {m['positive_rate']:.1%}

## Classification metrics (test set)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
{rows}

`persistence_baseline` predicts "congestion soon" whenever the current record already has an incident.
It shows how much the model adds by anticipating congestion *onset*.

## Edge format benchmark

| | scikit-learn (original) | ONNX Runtime (edge) |
|---|---|---|
| Model size | {size['sklearn_pickle'] / 1024:.1f} KiB | {size['onnx'] / 1024:.1f} KiB |
| Single prediction, mean | {s['mean']:.3f} ms | {o['mean']:.3f} ms |
| Single prediction, p95 | {s['p95']:.3f} ms | {o['p95']:.3f} ms |
| Batch of 1000, mean | {bs['mean']:.2f} ms | {bo['mean']:.2f} ms |

Max probability difference between the original and the ONNX model: {b['onnx_max_probability_difference']:.2e}.
Measured on: {b['hardware']}.
"""


if __name__ == "__main__":
    main()
