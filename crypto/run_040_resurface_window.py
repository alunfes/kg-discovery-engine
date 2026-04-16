"""Run 040: Resurface window extension — 120 min vs 240 min comparison.

Tests whether doubling resurface_window_min from 120 to 240 reduces
permanent archive loss without introducing noisy (low-value) resurfaces.

Background (Run 039 reference, window=120):
  - Recovery rate: 79.3% (357/450 archived)
  - Permanent loss: 93 (49 time-expired + 44 proximity miss)
  - Post-resurface value density: 90.5%

Metrics collected:
  recovery_rate          — fraction of archived cards that were resurfaced
  total_time_expired     — archived → pool age > archive_max_age, no match ever
  total_proximity_miss   — match arrived but AFTER resurface window expired
  avg_resurfaced_score   — quality check (noisy resurface risk if lower with w=240)
  pool_size_trajectory   — archive pool size over time

Usage:
  python -m crypto.run_040_resurface_window [--output-dir PATH]
"""
from __future__ import annotations

import copy
import csv
import json
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    _ARCHIVE_RATIO,
    _DIGEST_MAX,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    generate_cards,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUN_ID = "run_040_resurface_window"
SEED = 42
SESSION_HOURS = 7 * 24          # 168 h — 7-day crypto (24/7 market)
BATCH_INTERVAL_MIN = 30
N_CARDS_PER_BATCH = 20
CADENCE_MIN = 45
ARCHIVE_MAX_AGE_MIN = _DEFAULT_ARCHIVE_MAX_AGE_MIN  # 480 min
RESURFACE_WINDOWS = [120, 240]
NOISY_THRESHOLD = 0.60          # below = low-quality resurface

DEFAULT_OUT = (
    "crypto/artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"
)

# ---------------------------------------------------------------------------
# Simulation helpers — each function ≤ 40 lines
# ---------------------------------------------------------------------------


def _next_batch(rng: random.Random, n: int, ctr: list[int]) -> list[DeliveryCard]:
    """Generate n cards with globally unique IDs (avoids collision across batches).

    generate_cards() always produces c000–c019 regardless of seed, so without
    unique suffixes the archived_at dict keyed by card_id conflates cards from
    different batches.  ctr is a single-element list used as a mutable counter.
    """
    cards = generate_cards(seed=rng.randint(0, 9999), n_cards=n)
    for c in cards:
        ctr[0] += 1
        c.card_id = f"{ctr[0]}_{c.card_id}"
    return cards


def _build_deck(
    all_cards: list[tuple[float, DeliveryCard]],
    archived_at: dict[str, float],
    t: float,
    max_age: int,
) -> list[DeliveryCard]:
    """Return shallow copies of cards still within max_age of creation."""
    deck: list[DeliveryCard] = []
    for (ct, card) in all_cards:
        age = t - ct
        if age > max_age:
            continue
        c = copy.copy(card)
        c.age_min = age
        c.archived_at_min = archived_at.get(card.card_id)
        deck.append(c)
    return deck


def _apply_archive(
    deck: list[DeliveryCard],
    t: float,
    archived_at: dict[str, float],
    pool: dict[str, tuple[DeliveryCard, float]],
    catalog: dict[str, dict],
) -> None:
    """Transition expired cards to archived state; update pool and catalog."""
    for c in deck:
        if c.archived_at_min is not None:
            continue
        ratio = c.age_min / max(c.half_life_min, 1.0)
        if ratio < _DIGEST_MAX or c.age_min < _ARCHIVE_RATIO * c.half_life_min:
            continue
        archived_at[c.card_id] = t
        pool[c.card_id] = (c, t)
        catalog[c.card_id] = {
            "archived_at": t,
            "family": (c.branch, c.grammar_family),
            "composite_score": c.composite_score,
            "tier": c.tier,
        }


def _prune_pool(
    pool: dict[str, tuple[DeliveryCard, float]],
    t: float,
    max_age: int,
    pm_ids: set[str],
    rs_ids: set[str],
    te_ids: set[str],
) -> None:
    """Hard-delete archive pool entries older than max_age since archival."""
    to_del = [
        cid for cid, (_, at) in pool.items() if (t - at) > max_age
    ]
    for cid in to_del:
        if cid not in rs_ids and cid not in pm_ids:
            te_ids.add(cid)
        del pool[cid]


def _check_resurface(
    new_batch: list[DeliveryCard],
    pool: dict[str, tuple[DeliveryCard, float]],
    t: float,
    window: int,
    rs_ids: set[str],
    rs_scores: list[float],
    pm_ids: set[str],
    pm_events: list[dict],
) -> None:
    """Match incoming cards against archive pool; resurface or log proximity miss."""
    by_family: dict[tuple, list] = {}
    for cid, (card, at) in pool.items():
        key = (card.branch, card.grammar_family)
        by_family.setdefault(key, []).append((cid, card, at))

    triggered: set[tuple] = set()
    for inc in new_batch:
        key = (inc.branch, inc.grammar_family)
        if key not in by_family:
            continue
        in_win, out_win = [], []
        for (cid, card, at) in by_family[key]:
            (in_win if (t - at) <= window else out_win).append((cid, card, at))

        for (cid, card, at) in out_win:
            if cid not in rs_ids:
                pm_ids.add(cid)
                pm_events.append({
                    "card_id": cid, "archived_at": at,
                    "match_at": t, "age_at_match": t - at,
                    "composite_score": card.composite_score,
                })

        if in_win and key not in triggered:
            in_win.sort(key=lambda x: x[1].composite_score, reverse=True)
            cid, card, _ = in_win[0]
            rs_ids.add(cid)
            rs_scores.append(card.composite_score)
            del pool[cid]
            triggered.add(key)


def _final_metrics(
    catalog: dict[str, dict],
    rs_ids: set[str],
    rs_scores: list[float],
    pm_ids: set[str],
    te_ids: set[str],
    pool: dict[str, tuple[DeliveryCard, float]],
    window: int,
    total_generated: int,
) -> dict[str, Any]:
    """Classify remaining pool cards and compute final aggregate metrics."""
    for cid in pool:
        if cid not in rs_ids and cid not in pm_ids:
            te_ids.add(cid)

    n_arch = len(catalog)
    n_rs = len(rs_ids)
    n_pm = len(pm_ids - rs_ids)
    n_te = len(te_ids)
    recovery = n_rs / max(n_arch, 1)
    avg_rs = sum(rs_scores) / max(len(rs_scores), 1)
    avg_arch = sum(v["composite_score"] for v in catalog.values()) / max(n_arch, 1)
    noisy = sum(1 for s in rs_scores if s < NOISY_THRESHOLD)

    return {
        "resurface_window_min": window,
        "total_generated": total_generated,
        "total_archived": n_arch,
        "total_resurfaced": n_rs,
        "total_permanent_loss": n_pm + n_te,
        "total_time_expired": n_te,
        "total_proximity_miss": n_pm,
        "recovery_rate": round(recovery, 4),
        "avg_resurfaced_score": round(avg_rs, 4),
        "avg_archived_score": round(avg_arch, 4),
        "value_density_ratio": round(avg_rs / max(avg_arch, 1e-9), 4),
        "noisy_resurface_count": noisy,
        "noisy_resurface_rate": round(noisy / max(len(rs_scores), 1), 4),
    }


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------


def simulate_with_tracking(
    seed: int,
    session_hours: int,
    window: int,
    archive_max_age: int = ARCHIVE_MAX_AGE_MIN,
    batch_interval: int = BATCH_INTERVAL_MIN,
    n_per_batch: int = N_CARDS_PER_BATCH,
    cadence: int = CADENCE_MIN,
) -> tuple[dict[str, Any], list[tuple[float, int]], list[dict]]:
    """Run full batch-refresh simulation with archive tracking.

    Args:
        seed:           RNG seed for reproducibility.
        session_hours:  Total simulation duration in hours.
        window:         resurface_window_min to test.
        archive_max_age: Hard deletion threshold for archive pool (minutes).
        batch_interval: Minutes between new card batches.
        n_per_batch:    Cards per batch.
        cadence:        Review cadence in minutes.

    Returns:
        (metrics_dict, pool_size_history, proximity_miss_events)
    """
    session_min = session_hours * 60
    rng = random.Random(seed)
    ctr: list[int] = [0]  # mutable counter for unique card IDs across batches

    all_cards: list[tuple[float, DeliveryCard]] = []
    for c in _next_batch(rng, n_per_batch, ctr):
        all_cards.append((0.0, c))

    batch_times = list(range(batch_interval, session_min + 1, batch_interval))
    archived_at: dict[str, float] = {}
    pool: dict[str, tuple[DeliveryCard, float]] = {}
    catalog: dict[str, dict] = {}
    rs_ids: set[str] = set()
    rs_scores: list[float] = []
    pm_ids: set[str] = set()
    pm_events: list[dict] = []
    te_ids: set[str] = set()
    pool_history: list[tuple[float, int]] = []

    review_set = set(range(cadence, session_min + 1, cadence))
    next_idx = 0

    for t in sorted(set(batch_times) | review_set):
        new_batch: list[DeliveryCard] = []
        while next_idx < len(batch_times) and batch_times[next_idx] <= t:
            bt = float(batch_times[next_idx])
            for c in _next_batch(rng, n_per_batch, ctr):
                all_cards.append((bt, c))
                new_batch.append(c)
            next_idx += 1
        deck = _build_deck(all_cards, archived_at, float(t), archive_max_age)
        _apply_archive(deck, float(t), archived_at, pool, catalog)

        if t not in review_set:
            pool_history.append((float(t), len(pool)))
            continue

        _prune_pool(pool, float(t), archive_max_age, pm_ids, rs_ids, te_ids)
        _check_resurface(new_batch, pool, float(t), window,
                         rs_ids, rs_scores, pm_ids, pm_events)
        pool_history.append((float(t), len(pool)))

    metrics = _final_metrics(
        catalog, rs_ids, rs_scores, pm_ids, te_ids, pool,
        window, len(all_cards),
    )
    return metrics, pool_history, pm_events


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def write_comparison_json(results: list[dict], out_dir: str) -> None:
    """Write window_comparison.json with side-by-side metrics."""
    w120 = next(r for r in results if r["resurface_window_min"] == 120)
    w240 = next(r for r in results if r["resurface_window_min"] == 240)

    delta = {
        "recovery_rate_delta": round(w240["recovery_rate"] - w120["recovery_rate"], 4),
        "permanent_loss_delta": w240["total_permanent_loss"] - w120["total_permanent_loss"],
        "time_expired_delta": w240["total_time_expired"] - w120["total_time_expired"],
        "proximity_miss_delta": w240["total_proximity_miss"] - w120["total_proximity_miss"],
        "resurfaced_delta": w240["total_resurfaced"] - w120["total_resurfaced"],
        "value_density_delta": round(
            w240["value_density_ratio"] - w120["value_density_ratio"], 4
        ),
        "noisy_rate_delta": round(
            w240["noisy_resurface_rate"] - w120["noisy_resurface_rate"], 4
        ),
    }

    payload = {"window_120": w120, "window_240": w240, "delta_240_minus_120": delta}
    path = os.path.join(out_dir, "window_comparison.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  → {path}")


def write_pool_trajectory_csv(
    results: list[dict],
    histories: list[list[tuple[float, int]]],
    out_dir: str,
) -> None:
    """Write pool_size_trajectory.csv with one row per event time."""
    # Merge both histories by time
    combined: dict[float, dict] = {}
    for r, hist in zip(results, histories):
        w = r["resurface_window_min"]
        for (t, sz) in hist:
            combined.setdefault(t, {})["t"] = t
            combined[t][f"pool_w{w}"] = sz

    path = os.path.join(out_dir, "pool_size_trajectory.csv")
    fields = ["t", "pool_w120", "pool_w240"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for t in sorted(combined):
            writer.writerow(combined[t])
    print(f"  → {path}")


def write_run_config(out_dir: str) -> None:
    """Write run_config.json."""
    config = {
        "run_id": RUN_ID,
        "seed": SEED,
        "session_hours": SESSION_HOURS,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards_per_batch": N_CARDS_PER_BATCH,
        "cadence_min": CADENCE_MIN,
        "archive_max_age_min": ARCHIVE_MAX_AGE_MIN,
        "resurface_windows_tested": RESURFACE_WINDOWS,
        "noisy_threshold": NOISY_THRESHOLD,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = os.path.join(out_dir, "run_config.json")
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  → {path}")


def write_review_memo(results: list[dict], out_dir: str) -> None:
    """Write review_memo.md with analysis and recommendation."""
    w120 = next(r for r in results if r["resurface_window_min"] == 120)
    w240 = next(r for r in results if r["resurface_window_min"] == 240)

    rr_delta = round((w240["recovery_rate"] - w120["recovery_rate"]) * 100, 2)
    pl_delta = w240["total_permanent_loss"] - w120["total_permanent_loss"]
    rr120_pct = round(w120["recovery_rate"] * 100, 1)
    rr240_pct = round(w240["recovery_rate"] * 100, 1)

    recommend = "window=240" if (
        rr_delta > 0
        and w240["noisy_resurface_rate"] <= w120["noisy_resurface_rate"] + 0.05
        and w240["value_density_ratio"] >= w120["value_density_ratio"] - 0.02
    ) else "window=120 (現状維持)"

    lines = [
        f"# Run 040 Review Memo — Resurface Window 120 vs 240",
        f"*Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} | Seed: {SEED} | "
        f"Session: {SESSION_HOURS}h ({SESSION_HOURS // 24} days)*",
        "",
        "## 実験目的",
        "",
        "resurface_window_min を 120→240 に拡張した場合の効果を定量評価。",
        "主な懸念: 永続損失の削減 vs noisy resurface の増加リスク。",
        "",
        "## 結果サマリ",
        "",
        "| 指標 | window=120 | window=240 | Δ (240-120) |",
        "|------|-----------|-----------|------------|",
        f"| 総生成カード数 | {w120['total_generated']} | {w240['total_generated']} | 0 |",
        f"| 総アーカイブ数 | {w120['total_archived']} | {w240['total_archived']} | "
        f"{w240['total_archived'] - w120['total_archived']} |",
        f"| 回収数 (resurfaced) | {w120['total_resurfaced']} | {w240['total_resurfaced']} | "
        f"+{w240['total_resurfaced'] - w120['total_resurfaced']} |",
        f"| **回収率** | **{rr120_pct}%** | **{rr240_pct}%** | "
        f"**{'+' if rr_delta >= 0 else ''}{rr_delta}pp** |",
        f"| 永続損失 | {w120['total_permanent_loss']} | {w240['total_permanent_loss']} | "
        f"{'+' if pl_delta >= 0 else ''}{pl_delta} |",
        f"| └ time-expired | {w120['total_time_expired']} | {w240['total_time_expired']} | "
        f"{w240['total_time_expired'] - w120['total_time_expired']} |",
        f"| └ proximity miss | {w120['total_proximity_miss']} | {w240['total_proximity_miss']} | "
        f"{w240['total_proximity_miss'] - w120['total_proximity_miss']} |",
        f"| avg resurfaced score | {w120['avg_resurfaced_score']:.4f} | "
        f"{w240['avg_resurfaced_score']:.4f} | "
        f"{round(w240['avg_resurfaced_score'] - w120['avg_resurfaced_score'], 4)} |",
        f"| value density ratio | {w120['value_density_ratio']:.4f} | "
        f"{w240['value_density_ratio']:.4f} | "
        f"{round(w240['value_density_ratio'] - w120['value_density_ratio'], 4)} |",
        f"| noisy resurface rate | {w120['noisy_resurface_rate']:.4f} | "
        f"{w240['noisy_resurface_rate']:.4f} | "
        f"{round(w240['noisy_resurface_rate'] - w120['noisy_resurface_rate'], 4)} |",
        "",
        "## 解釈",
        "",
        f"- **回収率**: window=240 は {rr120_pct}% → {rr240_pct}%（{'+' if rr_delta >= 0 else ''}{rr_delta}pp）",
        f"- **永続損失**: {w120['total_permanent_loss']} → {w240['total_permanent_loss']} "
        f"({'減少' if pl_delta < 0 else '増加' if pl_delta > 0 else '変化なし'})",
        f"- **proximity miss 削減**: {w120['total_proximity_miss']} → {w240['total_proximity_miss']}",
        f"  - ウィンドウ拡張で {w120['total_proximity_miss'] - w240['total_proximity_miss']} 件が回収に転換",
        f"- **Noisy resurface**: rate {w120['noisy_resurface_rate']:.3f} → {w240['noisy_resurface_rate']:.3f}",
        f"  - スコア{NOISY_THRESHOLD}未満の低品質 resurface が"
        f"{'増加' if w240['noisy_resurface_count'] > w120['noisy_resurface_count'] else '減少・同水準'}",
        "",
        "## 判定",
        "",
        f"**推奨: {recommend}**",
        "",
        "判定基準:",
        "- 回収率改善 > 0pp → 有益",
        "- noisy_resurface_rate の増加 ≤ 5pp → 許容範囲",
        "- value_density_ratio の低下 ≤ 2% → 品質維持",
        "",
        "## アーティファクト",
        "",
        "| ファイル | 内容 |",
        "|---------|------|",
        "| window_comparison.json | window=120/240 の比較メトリクス |",
        "| pool_size_trajectory.csv | 時系列アーカイブプールサイズ |",
        "| run_config.json | 実験設定 |",
    ]

    path = os.path.join(out_dir, "review_memo.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_doc(results: list[dict], doc_path: str) -> None:
    """Write docs/run040_resurface_window_extension.md."""
    w120 = next(r for r in results if r["resurface_window_min"] == 120)
    w240 = next(r for r in results if r["resurface_window_min"] == 240)

    rr120_pct = round(w120["recovery_rate"] * 100, 1)
    rr240_pct = round(w240["recovery_rate"] * 100, 1)
    rr_delta = round((w240["recovery_rate"] - w120["recovery_rate"]) * 100, 2)
    recommend = "window=240 を採用" if rr_delta > 0 else "window=120 を維持"

    lines = [
        f"# Run 040: Resurface Window Extension (120 → 240 min)",
        "",
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ",
        f"**Seed**: {SEED}  ",
        f"**Session**: {SESSION_HOURS}h ({SESSION_HOURS // 24} days, 24/7 crypto)  ",
        f"**Config**: batch_interval={BATCH_INTERVAL_MIN}min, n_per_batch={N_CARDS_PER_BATCH}, "
        f"cadence={CADENCE_MIN}min, archive_max_age={ARCHIVE_MAX_AGE_MIN}min",
        "",
        "## 背景と動機",
        "",
        "Run 028 で採用した archive lifecycle では `resurface_window_min=120` を標準設定とした。",
        "理由: HL=40min (actionable_watch) の 2–3 サイクルをカバーし、",
        "パターン再現を確認として扱える十分なウィンドウ。",
        "",
        "しかし 7 日間運用シミュレーションで永続損失の内訳を分析すると、",
        "proximity miss（マッチが遅れてウィンドウ外で到達）が損失の大きな割合を占めることが",
        "Run 039 の分析で示された。ウィンドウを 240 min に拡張することで",
        "この proximity miss を一部回収できると仮説する。",
        "",
        "## 仮説",
        "",
        "- **H_WIN**: window=240 は window=120 より回収率が高い（proximity miss が減少）",
        "- **H_QUALITY**: window 拡張後も resurfaced card の品質（avg score）は維持される",
        "  （noisy_resurface_rate の上昇は ≤5pp）",
        "",
        "## 方法",
        "",
        f"- `simulate_with_tracking()` を seed={SEED}, window∈{{120, 240}} で実行",
        f"- 7日間 ({SESSION_HOURS}h) 連続シミュレーション（crypto は 24/7）",
        "- 各アーカイブカードの末路を追跡:",
        "  - **resurfaced**: 同 family の新規カードがウィンドウ内に到達",
        "  - **proximity miss**: 同 family の新規カードがウィンドウ外（後）に到達",
        "  - **time-expired**: archive_max_age 経過まで同 family が未到達",
        "",
        "## 結果",
        "",
        "| 指標 | window=120 | window=240 | Δ |",
        "|------|-----------|-----------|---|",
        f"| 回収率 | {rr120_pct}% | {rr240_pct}% | "
        f"{'+' if rr_delta >= 0 else ''}{rr_delta}pp |",
        f"| 永続損失 | {w120['total_permanent_loss']} | {w240['total_permanent_loss']} | "
        f"{w240['total_permanent_loss'] - w120['total_permanent_loss']} |",
        f"| └ time-expired | {w120['total_time_expired']} | {w240['total_time_expired']} | "
        f"{w240['total_time_expired'] - w120['total_time_expired']} |",
        f"| └ proximity miss | {w120['total_proximity_miss']} | {w240['total_proximity_miss']} | "
        f"{w240['total_proximity_miss'] - w120['total_proximity_miss']} |",
        f"| avg resurfaced score | {w120['avg_resurfaced_score']:.4f} | "
        f"{w240['avg_resurfaced_score']:.4f} | "
        f"{round(w240['avg_resurfaced_score'] - w120['avg_resurfaced_score'], 4)} |",
        f"| value density ratio | {w120['value_density_ratio']:.4f} | "
        f"{w240['value_density_ratio']:.4f} | "
        f"{round(w240['value_density_ratio'] - w120['value_density_ratio'], 4)} |",
        f"| noisy resurface rate | {w120['noisy_resurface_rate']:.3f} | "
        f"{w240['noisy_resurface_rate']:.3f} | "
        f"{round(w240['noisy_resurface_rate'] - w120['noisy_resurface_rate'], 3)} |",
        "",
        "## 仮説検証",
        "",
        f"- **H_WIN**: {'CONFIRMED' if rr_delta > 0 else 'NOT CONFIRMED'} — "
        f"回収率 {'+' if rr_delta >= 0 else ''}{rr_delta}pp",
        "- **H_QUALITY**: "
        + ("CONFIRMED" if w240["noisy_resurface_rate"] <= w120["noisy_resurface_rate"] + 0.05
           else "NOT CONFIRMED")
        + f" — noisy rate delta = "
        + f"{round(w240['noisy_resurface_rate'] - w120['noisy_resurface_rate'], 3)}",
        "",
        "## 推奨",
        "",
        f"**{recommend}**",
        "",
        "### 根拠",
        f"- proximity miss の削減: {w120['total_proximity_miss']} → {w240['total_proximity_miss']} "
        f"({w120['total_proximity_miss'] - w240['total_proximity_miss']} 件回収)",
        f"- value density の変化: {w120['value_density_ratio']:.4f} → {w240['value_density_ratio']:.4f}",
        f"- noisy resurface の変化: {w120['noisy_resurface_rate']:.3f} → {w240['noisy_resurface_rate']:.3f}",
        "",
        "### delivery_state.py への変更",
        "",
        "採用の場合、`delivery_state.py` の定数を更新:",
        "```python",
        "# Before",
        "_DEFAULT_RESURFACE_WINDOW_MIN: int = 120",
        "# After",
        "_DEFAULT_RESURFACE_WINDOW_MIN: int = 240",
        "```",
        "",
        "## 制約",
        "",
        "- シミュレーションは合成データ（実際の Hyperliquid マーケットデータではない）",
        "- batch_interval=30min の固定（実環境では可変）",
        "- resurface は review time + batch 到着の同時発生時のみ発火（cadence の離散化効果あり）",
    ]

    os.makedirs(os.path.dirname(doc_path), exist_ok=True)
    with open(doc_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {doc_path}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run 040: compare resurface_window_min = 120 vs 240."""
    import argparse
    parser = argparse.ArgumentParser(description="Run 040: resurface window comparison")
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    args = parser.parse_args()
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== {RUN_ID} ===")
    print(f"Seed: {SEED} | Session: {SESSION_HOURS}h ({SESSION_HOURS // 24} days)")
    print(f"Windows: {RESURFACE_WINDOWS} min | Output: {out_dir}\n")

    all_results: list[dict] = []
    all_histories: list[list[tuple[float, int]]] = []

    for window in RESURFACE_WINDOWS:
        print(f"Running window={window}min ...")
        metrics, history, _ = simulate_with_tracking(
            seed=SEED,
            session_hours=SESSION_HOURS,
            window=window,
        )
        all_results.append(metrics)
        all_histories.append(history)

        rr_pct = round(metrics["recovery_rate"] * 100, 1)
        print(f"  archived={metrics['total_archived']} "
              f"resurfaced={metrics['total_resurfaced']} "
              f"recovery={rr_pct}%")
        print(f"  permanent_loss={metrics['total_permanent_loss']} "
              f"(time_expired={metrics['total_time_expired']} "
              f"proximity_miss={metrics['total_proximity_miss']})")
        print(f"  avg_resurfaced_score={metrics['avg_resurfaced_score']:.4f} "
              f"value_density={metrics['value_density_ratio']:.4f} "
              f"noisy_rate={metrics['noisy_resurface_rate']:.3f}\n")

    w120 = next(r for r in all_results if r["resurface_window_min"] == 120)
    w240 = next(r for r in all_results if r["resurface_window_min"] == 240)
    rr_delta = round((w240["recovery_rate"] - w120["recovery_rate"]) * 100, 2)
    print(f"=== Delta (240 - 120) ===")
    print(f"  recovery_rate: {'+' if rr_delta >= 0 else ''}{rr_delta}pp")
    print(f"  permanent_loss: {w240['total_permanent_loss'] - w120['total_permanent_loss']}")
    print(f"  proximity_miss: {w240['total_proximity_miss'] - w120['total_proximity_miss']}")
    print(f"  noisy_rate: "
          f"{round(w240['noisy_resurface_rate'] - w120['noisy_resurface_rate'], 3)}\n")

    print("Writing artifacts ...")
    write_comparison_json(all_results, out_dir)
    write_pool_trajectory_csv(all_results, all_histories, out_dir)
    write_run_config(out_dir)
    write_review_memo(all_results, out_dir)

    doc_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "run040_resurface_window_extension.md"
    )
    write_doc(all_results, doc_path)
    print(f"\n=== {RUN_ID} complete ===")


if __name__ == "__main__":
    main()
