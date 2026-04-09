#!/usr/bin/env python3
"""Benchmark all generator and judge models via the backend LLM benchmark API.

Reads config/generators.yaml and config/judges.yaml to extract the unique
set of (vendor, model) pairs, then triggers POST /v1/admin/llm-benchmark/run
for each model N times to build statistically meaningful data.

Usage:
    python scripts/benchmark_models.py [OPTIONS]

Options:
    --runs N            Number of benchmark runs per model (default: 3)
    --question-ids ID   Comma-separated list of question IDs for fixed sets
    --dry-run           Preview which models would be benchmarked
    --api-url URL       Backend API URL (default: $BACKEND_API_URL or production)
    --admin-token TOK   Admin token (default: $ADMIN_TOKEN)
    --help              Show this help message

Exit codes:
    0 - All runs completed successfully
    1 - Some runs failed
    2 - Configuration or setup error
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx
import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"
DEFAULT_API_URL = "https://aiq-backend-production.up.railway.app"
BENCHMARK_ENDPOINT = "/v1/admin/llm-benchmark/run"


def load_models_from_configs() -> List[Tuple[str, str]]:
    """Extract unique (vendor, model) pairs from generators.yaml and judges.yaml."""
    seen: Set[Tuple[str, str]] = set()
    models: List[Tuple[str, str]] = []

    generators_path = CONFIG_DIR / "generators.yaml"
    judges_path = CONFIG_DIR / "judges.yaml"

    if not generators_path.exists():
        print(f"Error: {generators_path} not found", file=sys.stderr)
        sys.exit(2)
    if not judges_path.exists():
        print(f"Error: {judges_path} not found", file=sys.stderr)
        sys.exit(2)

    with open(generators_path) as f:
        gen_config = yaml.safe_load(f)

    with open(judges_path) as f:
        judge_config = yaml.safe_load(f)

    # Extract from generators (primary + fallback)
    for _type, cfg in gen_config.get("generators", {}).items():
        pair = (cfg["provider"], cfg["model"])
        if pair not in seen:
            seen.add(pair)
            models.append(pair)
        if "fallback" in cfg and "fallback_model" in cfg:
            fb = (cfg["fallback"], cfg["fallback_model"])
            if fb not in seen:
                seen.add(fb)
                models.append(fb)

    # Extract from default generator
    if "default_generator" in gen_config:
        dg = gen_config["default_generator"]
        pair = (dg["provider"], dg["model"])
        if pair not in seen:
            seen.add(pair)
            models.append(pair)
        if "fallback" in dg and "fallback_model" in dg:
            fb = (dg["fallback"], dg["fallback_model"])
            if fb not in seen:
                seen.add(fb)
                models.append(fb)

    # Extract from judges (primary + fallback)
    for _type, cfg in judge_config.get("judges", {}).items():
        pair = (cfg["provider"], cfg["model"])
        if pair not in seen:
            seen.add(pair)
            models.append(pair)
        if "fallback" in cfg and "fallback_model" in cfg:
            fb = (cfg["fallback"], cfg["fallback_model"])
            if fb not in seen:
                seen.add(fb)
                models.append(fb)

    # Extract from default judge
    if "default_judge" in judge_config:
        dj = judge_config["default_judge"]
        pair = (dj["provider"], dj["model"])
        if pair not in seen:
            seen.add(pair)
            models.append(pair)
        if "fallback" in dj and "fallback_model" in dj:
            fb = (dj["fallback"], dj["fallback_model"])
            if fb not in seen:
                seen.add(fb)
                models.append(fb)

    return models


def print_model_table(models: List[Tuple[str, str]], runs: int) -> None:
    """Print the set of models that will be benchmarked."""
    header = f"{'#':<4} {'Vendor':<12} {'Model':<35} {'Runs':<6}"
    print(header)
    print("-" * len(header))
    for i, (vendor, model) in enumerate(models, 1):
        print(f"{i:<4} {vendor:<12} {model:<35} {runs:<6}")
    print(
        f"\nTotal: {len(models)} models x {runs} runs = {len(models) * runs} benchmark runs"
    )


def run_benchmark(
    client: httpx.Client,
    api_url: str,
    admin_token: str,
    vendor: str,
    model_id: str,
    question_ids: Optional[List[int]],
) -> Dict:
    """Trigger a single benchmark run and return the response."""
    payload: Dict = {"vendor": vendor, "model_id": model_id}
    if question_ids:
        payload["question_ids"] = question_ids

    resp = client.post(
        f"{api_url}{BENCHMARK_ENDPOINT}",
        json=payload,
        headers={"X-Admin-Token": admin_token},
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.json()


def print_summary(results: List[Dict]) -> None:
    """Print a summary table of all triggered runs."""
    header = (
        f"{'#':<4} {'Vendor':<12} {'Model':<35} "
        f"{'Run':<5} {'Session':<10} {'Status':<12}"
    )
    print(f"\n{'=' * len(header)}")
    print("Benchmark Summary")
    print(f"{'=' * len(header)}")
    print(header)
    print("-" * len(header))

    success = 0
    failed = 0
    for i, r in enumerate(results, 1):
        status = r.get("status", "error")
        session = str(r.get("session_id", "-"))
        if status == "completed":
            success += 1
        else:
            failed += 1
        print(
            f"{i:<4} {r['vendor']:<12} {r['model_id']:<35} "
            f"{r['run_num']:<5} {session:<10} {status:<12}"
        )

    print(f"\nCompleted: {success}  Failed: {failed}  Total: {len(results)}")


def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description="Benchmark question-service generator and judge models"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of benchmark runs per model (default: 3)",
    )
    parser.add_argument(
        "--question-ids",
        type=str,
        default=None,
        help="Comma-separated list of question IDs for a fixed question set",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which models would be benchmarked without triggering runs",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=os.environ.get("BACKEND_API_URL", DEFAULT_API_URL),
        help="Backend API URL (default: $BACKEND_API_URL or production URL)",
    )
    parser.add_argument(
        "--admin-token",
        type=str,
        default=os.environ.get("ADMIN_TOKEN", ""),
        help="Admin token for API authentication (default: $ADMIN_TOKEN)",
    )
    args = parser.parse_args()

    # Parse question IDs if provided
    question_ids: Optional[List[int]] = None
    if args.question_ids:
        try:
            question_ids = [int(x.strip()) for x in args.question_ids.split(",")]
        except ValueError:
            print(
                "Error: --question-ids must be comma-separated integers",
                file=sys.stderr,
            )
            sys.exit(2)

    models = load_models_from_configs()
    if not models:
        print("Error: no models found in config files", file=sys.stderr)
        sys.exit(2)

    print(f"Models extracted from config ({len(models)} unique):\n")
    print_model_table(models, args.runs)

    if args.dry_run:
        print("\n[DRY RUN] No benchmark runs triggered.")
        if question_ids:
            print(f"Would use fixed question set: {question_ids}")
        sys.exit(0)

    if not args.admin_token:
        print(
            "Error: --admin-token or $ADMIN_TOKEN required for live runs",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"\nTarget: {args.api_url}")
    if question_ids:
        print(f"Fixed question set: {question_ids}")
    print(f"Starting {len(models) * args.runs} benchmark runs...\n")

    results: List[Dict] = []
    with httpx.Client() as client:
        for vendor, model_id in models:
            for run_num in range(1, args.runs + 1):
                label = f"{vendor}/{model_id} (run {run_num}/{args.runs})"
                print(f"  Triggering {label}...", end=" ", flush=True)
                start = time.monotonic()
                try:
                    resp = run_benchmark(
                        client,
                        args.api_url,
                        args.admin_token,
                        vendor,
                        model_id,
                        question_ids,
                    )
                    elapsed = time.monotonic() - start
                    results.append(
                        {
                            "vendor": vendor,
                            "model_id": model_id,
                            "run_num": run_num,
                            "session_id": resp.get("session_id"),
                            "status": resp.get("status", "unknown"),
                        }
                    )
                    print(f"done (session {resp.get('session_id')}, {elapsed:.1f}s)")
                except httpx.HTTPStatusError as exc:
                    elapsed = time.monotonic() - start
                    results.append(
                        {
                            "vendor": vendor,
                            "model_id": model_id,
                            "run_num": run_num,
                            "session_id": None,
                            "status": f"error ({exc.response.status_code})",
                        }
                    )
                    print(f"FAILED ({exc.response.status_code}, {elapsed:.1f}s)")
                except httpx.RequestError as exc:
                    elapsed = time.monotonic() - start
                    results.append(
                        {
                            "vendor": vendor,
                            "model_id": model_id,
                            "run_num": run_num,
                            "session_id": None,
                            "status": f"error ({type(exc).__name__})",
                        }
                    )
                    print(f"FAILED ({type(exc).__name__}, {elapsed:.1f}s)")

    print_summary(results)

    has_failures = any(not r.get("status", "").startswith("completed") for r in results)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
