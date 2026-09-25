"""Public, offline, ground-only command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bundle import make_bundle, verify_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ix-orbital-edge", description="Ground-only edge AI evaluation")
    sub = parser.add_subparsers(dest="operation", required=True)
    demo = sub.add_parser("demo", help="generate and audit a fully synthetic scenario")
    demo.add_argument("--output", type=Path, default=Path("demo-output"))
    demo.add_argument("--records", type=int, default=48)
    demo.add_argument("--seed", type=int, default=991)
    demo.add_argument("--threshold", type=float, default=0.6)
    demo.add_argument("--queue-bytes", type=int, default=2800)
    demo.add_argument("--outage-start", type=int, default=10)
    demo.add_argument("--outage-length", type=int, default=13)
    demo.add_argument("--downlink-usd-per-mib", type=float, default=25.0)
    demo.add_argument("--inference-mj", type=float, default=12.0)
    check = sub.add_parser("verify", help="check bundle digests and replay all decisions")
    check.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "demo":
            report = make_bundle(args.output, count=args.records, seed=args.seed,
                                 threshold=args.threshold, queue_bytes=args.queue_bytes,
                                 outage_start=args.outage_start, outage_length=args.outage_length,
                                 downlink=args.downlink_usd_per_mib, energy=args.inference_mj)
            verified = verify_bundle(args.output)
            result = {"output": str(args.output), "verified": verified["verified"],
                      "records": report["records"], "confusion": report["confusion"],
                      "serialization_reduction_fraction": report["serialization_reduction_fraction"],
                      "decision": report["decision"]}
        else:
            check_result = verify_bundle(args.bundle)
            result = {k: v for k, v in check_result.items() if k != "report"}
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"verification failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
