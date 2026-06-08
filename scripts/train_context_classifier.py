"""문맥 분류기 학습 (M3) — 순수 numpy L2 로지스틱 회귀.

data/context/*.jsonl(동음이의어 대조 셋: harmful=1/benign=0)으로 분류기를 학습해
models/context_clf.json(가중치+해시설정+버전)을 쓴다. 환경 제약(CPU·GPU 없음·
torch 미설치)상 KcELECTRA 풀 파인튜닝 대신 경량 LR로 1차 분류기를 만든다(docs/05 M3).

피처는 noise_checker.context_classifier.extract_features를 재사용한다(학습/서빙
피처 동기화). 학습:
  - train/val 80/20 **surface별 층화분할**(동음이의 표면 균형, 결정적 seed).
  - 클래스 가중 L2 LR, full-batch GD(데이터 < 1k행이라 충분·결정적).
  - val에서 **온도 스케일링**으로 확신도 캘리브레이션(시그모이드가 harmful 확률로
    의미 갖도록) + accuracy/precision/recall/AUC(근사) 출력.

산출 JSON은 희소(0 아닌 가중치만) — 해시 공간 2^18 전체 덤프 방지.

사용:
  uv run python scripts/train_context_classifier.py
  uv run python scripts/train_context_classifier.py --out models/context_clf.json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from noise_checker.context_classifier import (
    FEATURE_VERSION,
    extract_features,
    feature_dim,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "context"
DEFAULT_OUT = ROOT / "models" / "context_clf.json"
SEED = 20260608
VAL_FRACTION = 0.2


def _load_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(DATA_DIR.glob("contrastive-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"대조 셋이 비었습니다: {DATA_DIR}/contrastive-*.jsonl")
    return rows


def _stratified_split(rows: list[dict]) -> tuple[list[int], list[int]]:
    """surface별로 VAL_FRACTION을 검증에 배정하는 층화분할(결정적)."""
    rng = np.random.default_rng(SEED)
    by_surface: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_surface.setdefault(r["surface"], []).append(i)
    train_idx: list[int] = []
    val_idx: list[int] = []
    for surface in sorted(by_surface):
        idxs = by_surface[surface]
        perm = rng.permutation(len(idxs))
        n_val = max(1, round(len(idxs) * VAL_FRACTION)) if len(idxs) > 1 else 0
        for rank, p in enumerate(perm):
            (val_idx if rank < n_val else train_idx).append(idxs[p])
    return sorted(train_idx), sorted(val_idx)


def _build_matrix(rows: list[dict], idx: list[int]) -> tuple[list[dict[int, float]], np.ndarray]:
    feats = [extract_features(rows[i]["text"], rows[i]["surface"]) for i in idx]
    y = np.array([1.0 if rows[i]["label"] == "harmful" else 0.0 for i in idx])
    return feats, y


def _predict_z(feats: list[dict[int, float]], w: np.ndarray, b: float) -> np.ndarray:
    z = np.full(len(feats), b)
    for r, f in enumerate(feats):
        s = 0.0
        for j, v in f.items():
            s += w[j] * v
        z[r] += s
    return z


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def _train_lr(
    feats: list[dict[int, float]],
    y: np.ndarray,
    *,
    dim: int,
    l2: float,
    lr: float,
    epochs: int,
) -> tuple[np.ndarray, float]:
    """클래스 가중 L2 로지스틱 회귀, full-batch GD(결정적).

    클래스 가중 = 역빈도(소수 클래스 업웨이트). bias는 정규화하지 않는다.
    """
    n = len(feats)
    w = np.zeros(dim)
    b = 0.0
    pos = float(y.sum())
    neg = float(n - pos)
    # 역빈도 가중(평균 1로 정규화).
    w_pos = n / (2.0 * pos) if pos else 1.0
    w_neg = n / (2.0 * neg) if neg else 1.0
    sample_w = np.where(y == 1.0, w_pos, w_neg)
    for _ in range(epochs):
        p = _sigmoid(_predict_z(feats, w, b))
        err = (p - y) * sample_w
        grad_b = float(err.sum()) / n
        grad_w = np.zeros(dim)
        for r, f in enumerate(feats):
            er = err[r]
            if er == 0.0:
                continue
            for j, v in f.items():
                grad_w[j] += er * v
        grad_w /= n
        grad_w += l2 * w  # L2 (bias 제외)
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def _fit_temperature(z: np.ndarray, y: np.ndarray) -> float:
    """val 로짓에 온도 T를 맞춰 NLL 최소화(1D 그리드 + 보정) — 결정적."""
    best_t, best_nll = 1.0, float("inf")
    for t in np.linspace(0.5, 3.0, 51):
        p = np.clip(_sigmoid(z / t), 1e-6, 1 - 1e-6)
        nll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
        if nll < best_nll:
            best_nll, best_t = nll, float(t)
    return best_t


def _auc(scores: np.ndarray, y: np.ndarray) -> float:
    """ROC AUC = Mann-Whitney U / (n_pos*n_neg). 동점은 평균순위."""
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    pos = y == 1.0
    n_pos = float(pos.sum())
    n_neg = float((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _metrics(p: np.ndarray, y: np.ndarray, thr: float = 0.5) -> dict[str, float]:
    pred = (p >= thr).astype(float)
    tp = float(((pred == 1) & (y == 1)).sum())
    fp = float(((pred == 1) & (y == 0)).sum())
    fn = float(((pred == 0) & (y == 1)).sum())
    tn = float(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(y) if len(y) else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "auc": round(_auc(p, y), 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="문맥 분류기 학습 (numpy LR)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="가중치 JSON 출력 경로")
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--lr", type=float, default=0.5)
    parser.add_argument("--epochs", type=int, default=400)
    args = parser.parse_args(argv)

    rows = _load_rows()
    train_idx, val_idx = _stratified_split(rows)
    dim = feature_dim()

    tr_feats, tr_y = _build_matrix(rows, train_idx)
    va_feats, va_y = _build_matrix(rows, val_idx)

    w, b = _train_lr(
        tr_feats, tr_y, dim=dim, l2=args.l2, lr=args.lr, epochs=args.epochs
    )

    va_z = _predict_z(va_feats, w, b)
    temperature = _fit_temperature(va_z, va_y)

    tr_p = _sigmoid(_predict_z(tr_feats, w, b) / temperature)
    va_p = _sigmoid(va_z / temperature)
    train_metrics = _metrics(tr_p, tr_y)
    val_metrics = _metrics(va_p, va_y)

    # 희소 직렬화(0 아닌 가중치만).
    nz = np.nonzero(w)[0]
    weights = {int(j): float(w[j]) for j in nz}

    out = {
        "model_type": "numpy_logreg",
        "feature_version": FEATURE_VERSION,
        "data_version": datetime.now(UTC).date().isoformat(),
        "trained_at": datetime.now(UTC).isoformat(),
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_features_nonzero": len(weights),
        "hyperparams": {"l2": args.l2, "lr": args.lr, "epochs": args.epochs, "seed": SEED},
        "temperature": temperature,
        "bias": float(b),
        "weights": weights,
        "metrics": {"train": train_metrics, "val": val_metrics},
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"학습 완료: {out_path}")
    print(f"  train {len(train_idx)} / val {len(val_idx)}  비0 가중치 {len(weights)}")
    print(f"  온도 T={temperature:.3f}")
    print(f"  train {train_metrics}")
    print(f"  val   {val_metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
