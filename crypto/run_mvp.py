"""Run one MVP experiment using the crypto KG discovery pipeline."""

import sys
import os

# Ensure the worktree root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto.src.pipeline import PipelineConfig, run_pipeline


def main() -> None:
    """Execute the MVP pipeline run."""
    config = PipelineConfig(
        run_id="run_001_20260415",
        seed=42,
        n_minutes=120,
        assets=["HYPE", "ETH", "BTC", "SOL"],
        top_k=10,
        output_dir="crypto/artifacts/runs",
    )

    print(f"Starting pipeline run: {config.run_id}")
    print(f"Seed={config.seed}, n_minutes={config.n_minutes}, assets={config.assets}")
    print()

    cards = run_pipeline(config)

    print(f"Pipeline complete. Generated {len(cards)} hypothesis cards.")
    print()

    for i, card in enumerate(
        sorted(cards, key=lambda c: c.composite_score, reverse=True), 1
    ):
        print(f"  {i:2d}. [{card.composite_score:.3f}] [{card.secrecy_level.value[:7]}] "
              f"[{card.validation_status.value[:8]}] {card.title}")

    print()
    print(f"Output: crypto/artifacts/runs/{config.run_id}/")


if __name__ == "__main__":
    main()
