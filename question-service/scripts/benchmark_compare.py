#!/usr/bin/env python3
"""Fetch and display the human vs model benchmark comparison table.

Usage:
    python scripts/benchmark_compare.py [--api-url URL] [--admin-token TOKEN]
"""

import argparse
import os
import sys

import httpx


DEFAULT_API_URL = "https://aiq-backend-production.up.railway.app"


def main() -> None:
    parser = argparse.ArgumentParser(description="Display LLM benchmark comparison")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("BACKEND_API_URL", DEFAULT_API_URL),
    )
    parser.add_argument(
        "--admin-token",
        default=os.environ.get("ADMIN_TOKEN", ""),
    )
    args = parser.parse_args()

    if not args.admin_token:
        print("Error: --admin-token or $ADMIN_TOKEN required", file=sys.stderr)
        sys.exit(2)

    resp = httpx.get(
        f"{args.api_url}/v1/admin/llm-benchmark/compare",
        headers={"X-Admin-Token": args.admin_token},
        timeout=30.0,
    )
    resp.raise_for_status()
    d = resp.json()

    print("=" * 90)
    print("HUMAN vs MODEL BENCHMARK COMPARISON")
    print("=" * 90)

    print(f"\nHuman Avg IQ: {d['human_avg_iq']}")
    print(f"Human Tests:  {d['human_test_count']}")
    if d.get("human_ci"):
        ci = d["human_ci"]
        print(f"Human 95% CI: [{ci['lower']:.1f}, {ci['upper']:.1f}]")
    if d.get("low_sample_warning"):
        print(f"Warning:      {d['low_sample_warning']}")

    header = (
        f"{'Model':<40} {'IQ':>5} {'Mean IQ':>9} "
        f"{'95% CI':>18} {'Acc%':>6} {'Runs':>5} {'Q':>5}"
    )
    print(f"\n{header}")
    print("-" * 90)

    for m in sorted(d["models"], key=lambda x: x.get("mean_iq") or 0, reverse=True):
        name = f"{m['vendor']}/{m['model_id']}"
        iq = str(m["iq_score"]) if m.get("iq_score") else "-"
        mean = f"{m['mean_iq']:.1f}" if m.get("mean_iq") else "-"
        ci = ""
        if m.get("iq_ci"):
            ci = f"[{m['iq_ci']['lower']:.0f}, {m['iq_ci']['upper']:.0f}]"
        acc = (
            f"{m['correct_answers'] / m['total_questions'] * 100:.1f}"
            if m["total_questions"]
            else "-"
        )
        print(
            f"{name:<40} {iq:>5} {mean:>9} {ci:>18} "
            f"{acc:>6} {m['sessions_count']:>5} {m['total_questions']:>5}"
        )

    if d.get("domain_breakdown"):
        header = (
            f"\n{'Domain':<12} {'Human%':>8} {'Human N':>9} "
            f"{'Model%':>8} {'Model N':>9}"
        )
        print(header)
        print("-" * 50)
        for b in d["domain_breakdown"]:
            hp = f"{b['human_pct']:.1f}" if b.get("human_pct") is not None else "-"
            mp = f"{b['model_pct']:.1f}" if b.get("model_pct") is not None else "-"
            print(
                f"{b['domain']:<12} {hp:>8} {b['human_n']:>9} {mp:>8} {b['model_n']:>9}"
            )

    if d.get("effect_size") is not None:
        print(f"\nCohen's d (human vs model): {d['effect_size']:.2f}")


if __name__ == "__main__":
    main()
