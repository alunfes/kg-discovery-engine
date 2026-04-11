"""MVP Runner for Hyperliquid KG Discovery Engine.

Usage: python -m src.pipeline.mvp_runner [--real] [--symbols HYPE BTC ETH SOL] [--timeframe 1h]
By default uses MockMarketConnector. With --real, uses HttpMarketConnector.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import random

from src.ingestion.mock_connector import MockMarketConnector
from src.schema.market_state import MarketSnapshot, OHLCV, FundingRate
from src.schema.task_status import RunStatus
from src.schema.hypothesis_card import HypothesisCard
from src.kg.models import KnowledgeGraph, HypothesisCandidate
from src.kg.trading_builders import build_all_kgs
from src.states.state_extractor import build_market_snapshot
from src.operators.registry import run_full_pipeline
from src.eval.trading_scorer import score_and_convert_all
from src.inventory.hypothesis_store import HypothesisStore

_SEED = 42
_DEFAULT_SYMBOLS = ["HYPE", "BTC", "ETH", "SOL"]
_SYMBOL_MAP = {
    "HYPE": "HYPE/USDC:USDC",
    "BTC": "BTC/USDC:USDC",
    "ETH": "ETH/USDC:USDC",
    "SOL": "SOL/USDC:USDC",
}
_HOUR_MS = 3_600_000
_BASE_TS = 1_744_000_000_000


def setup_output_dir(run_id: str) -> str:
    """Create artifacts/runs/{run_id}/ directory at project root and return its path."""
    # src/pipeline/ -> src/ -> project_root/
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(src_dir)
    output_dir = os.path.join(project_root, "artifacts", "runs", run_id)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_input_summary(snapshot: MarketSnapshot, output_dir: str) -> None:
    """Write a markdown summary of loaded data to input_summary.md."""
    by_sym = snapshot.events_by_symbol()
    by_type = snapshot.events_by_type()
    lines = [
        "# Input Data Summary",
        f"- Duration: {snapshot.duration_ms() // _HOUR_MS}h",
        f"- Symbols: {', '.join(snapshot.symbols)}",
        f"- Total state events: {len(snapshot.events)}",
        "", "## Events by Symbol", "",
    ]
    for sym in sorted(by_sym):
        lines.append(f"- {sym}: {len(by_sym[sym])} events")
    lines += ["", "## Events by Type", ""]
    for st in sorted(by_type):
        lines.append(f"- {st}: {len(by_type[st])} events")
    path = os.path.join(output_dir, "input_summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_run_notes(
    kgs: dict[str, KnowledgeGraph],
    candidates: list[HypothesisCandidate],
    cards: list[HypothesisCard],
    run_status: RunStatus,
    output_dir: str,
) -> None:
    """Write markdown notes about KG sizes, operator chains, and results."""
    secrecy_counts: dict[str, int] = {}
    for card in cards:
        secrecy_counts[card.secrecy_level] = secrecy_counts.get(card.secrecy_level, 0) + 1
    lines = [
        "# Run Notes",
        f"- Run ID: {run_status.run_id}  Phase: {run_status.phase}",
        "", "## KG Sizes", "",
    ]
    for kg_name, kg in kgs.items():
        lines.append(f"- {kg_name}: {len(kg.nodes())} nodes, {len(kg.edges())} edges")
    lines += [
        "", "## Operator Pipeline", "",
        "1. Compose each KG individually (intra-domain)",
        "2. align+union microstructure+cross_asset -> compose",
        "3. align+union execution+regime -> compose",
        "4. regime-microstructure difference -> compose",
        "", "## Results", "",
        f"- Raw candidates: {len(candidates)}",
        f"- Hypothesis cards: {len(cards)}",
        "", "### Secrecy Distribution", "",
    ]
    for level, count in sorted(secrecy_counts.items()):
        lines.append(f"- {level}: {count}")
    if run_status.error:
        lines += ["", "## Error", "", run_status.error]
    path = os.path.join(output_dir, "run_notes.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _fetch_data(
    connector: MockMarketConnector,
    symbols: list[str],
    timeframe: str,
    max_candles: int,
) -> tuple[dict[str, list[OHLCV]], dict[str, list[FundingRate]]]:
    """Fetch OHLCV and funding data for all symbols."""
    end_ms = _BASE_TS + max_candles * _HOUR_MS
    candles_by_symbol: dict[str, list[OHLCV]] = {}
    funding_by_symbol: dict[str, list[FundingRate]] = {}

    for short_sym in symbols:
        full_sym = _SYMBOL_MAP.get(short_sym, short_sym)
        ohlcv = connector.get_ohlcv(full_sym, timeframe, _BASE_TS, end_ms)
        funding = connector.get_funding(full_sym, _BASE_TS, end_ms)
        if ohlcv:
            candles_by_symbol[short_sym] = ohlcv
            funding_by_symbol[short_sym] = funding

    return candles_by_symbol, funding_by_symbol


def _write_cards_json(cards: list[HypothesisCard], path: str) -> None:
    """Write a list of HypothesisCards as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in cards], f, indent=2, ensure_ascii=False)


def _write_artifacts(
    cards: list[HypothesisCard],
    output_dir: str,
) -> None:
    """Write all hypothesis card artifact files to output_dir."""
    all_path = os.path.join(output_dir, "generated_hypotheses.json")
    _write_cards_json(cards, all_path)

    by_secrecy: dict[str, list[HypothesisCard]] = {}
    for card in cards:
        by_secrecy.setdefault(card.secrecy_level, []).append(card)

    private = by_secrecy.get("private_alpha", [])
    if private:
        _write_cards_json(private, os.path.join(output_dir, "private_alpha_candidates.json"))

    shareable = by_secrecy.get("shareable_structure", [])
    if shareable:
        _write_cards_json(
            shareable, os.path.join(output_dir, "shareable_structure_candidates.json")
        )

    discarded = by_secrecy.get("discard", [])
    if discarded:
        _write_cards_json(discarded, os.path.join(output_dir, "discarded_candidates.json"))


def run_mvp(
    connector_type: str = "mock",
    symbols: list[str] | None = None,
    timeframe: str = "1h",
    output_dir: str | None = None,
    max_candles: int = 200,
) -> RunStatus:
    """Run the full MVP experiment end-to-end.

    Steps:
    1. Set up connector (mock or HTTP).
    2. Fetch OHLCV + funding data.
    3. Extract state events.
    4. Build 4 KGs.
    5. Run operator pipeline.
    6. Score and convert candidates to HypothesisCards.
    7. Store in inventory.
    8. Write artifact files to output_dir.
    9. Return RunStatus.
    """
    random.seed(_SEED)
    if symbols is None:
        symbols = list(_DEFAULT_SYMBOLS)

    now = datetime.datetime.utcnow()
    run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_hyperliquid_mvp"
    started_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    status = RunStatus.new(
        run_id=run_id, started_at=started_at, symbols=symbols, timeframe=timeframe
    )

    if output_dir is None:
        output_dir = setup_output_dir(run_id)

    try:
        # Step 1: connector
        if connector_type == "mock":
            connector = MockMarketConnector()
        else:
            from src.ingestion.http_connector import HttpMarketConnector
            connector = HttpMarketConnector()

        # Step 2: fetch data
        status.phase = "ingestion"
        candles_by_sym, funding_by_sym = _fetch_data(
            connector, symbols, timeframe, max_candles
        )
        status.n_candles_loaded = sum(len(v) for v in candles_by_sym.values())

        # Step 3: extract state events
        status.phase = "state_extraction"
        snapshot = build_market_snapshot(candles_by_sym, funding_by_sym)
        status.n_state_events = len(snapshot.events)

        # Step 4: build KGs
        status.phase = "kg_build"
        kgs = build_all_kgs(snapshot, symbols)
        status.n_kg_nodes = {name: len(kg.nodes()) for name, kg in kgs.items()}

        # Step 5: run operator pipeline
        status.phase = "operator"
        candidates = run_full_pipeline(kgs, max_depth=3)
        status.n_candidates = len(candidates)

        # Step 6: score and convert
        status.phase = "evaluation"
        cards = score_and_convert_all(candidates, symbols, timeframe, run_id)

        # Step 7: store in inventory
        store_dir = os.path.join(output_dir, "inventory")
        store = HypothesisStore(store_dir)
        store.save_batch(cards)
        status.n_hypotheses_stored = len(cards)

        # Step 8: write artifacts
        write_input_summary(snapshot, output_dir)
        _write_artifacts(cards, output_dir)
        write_run_notes(kgs, candidates, cards, status, output_dir)

        status.phase = "complete"
        status.completed_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        status.notes = f"output_dir={output_dir}"

    except Exception as exc:
        status.phase = "failed"
        status.error = str(exc)
        status.completed_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KG Discovery Engine MVP Runner")
    parser.add_argument(
        "--real", action="store_true", help="Use HttpMarketConnector instead of mock"
    )
    parser.add_argument(
        "--symbols", nargs="+", default=_DEFAULT_SYMBOLS,
        metavar="SYM", help="Symbols to process (e.g. HYPE BTC ETH SOL)"
    )
    parser.add_argument(
        "--timeframe", default="1h", help="Candle timeframe (default: 1h)"
    )
    parser.add_argument(
        "--max-candles", type=int, default=200, help="Max OHLCV candles per symbol"
    )
    parser.add_argument(
        "--output-dir", default=None, help="Override output directory"
    )
    args = parser.parse_args()

    connector_type = "http" if args.real else "mock"
    result = run_mvp(
        connector_type=connector_type,
        symbols=args.symbols,
        timeframe=args.timeframe,
        output_dir=args.output_dir,
        max_candles=args.max_candles,
    )

    print(f"Run ID   : {result.run_id}")
    print(f"Phase    : {result.phase}")
    print(f"Candles  : {result.n_candles_loaded}")
    print(f"Events   : {result.n_state_events}")
    print(f"KG nodes : {result.n_kg_nodes}")
    print(f"Candidates: {result.n_candidates}")
    print(f"Cards stored: {result.n_hypotheses_stored}")
    if result.error:
        print(f"ERROR    : {result.error}")
    if result.notes:
        print(f"Notes    : {result.notes}")
