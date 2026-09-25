"""Offline, ground-evaluation command line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature

from .bundle import make_bundle, verify_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ix-orbital-edge",
        description="Mission-assurance control-plane evaluation for spacecraft edge autonomy",
    )
    sub = parser.add_subparsers(dest="operation", required=True)
    demo = sub.add_parser("demo", help="generate a signed synthetic mission-assurance evidence bundle")
    demo.add_argument("--output", type=Path, default=Path("demo-output"))
    demo.add_argument("--records", type=int, default=60)
    demo.add_argument("--seed", type=int, default=991)
    demo.add_argument("--threshold", type=float, default=0.6)
    demo.add_argument("--queue-bytes", type=int, default=6500)
    demo.add_argument("--outage-start", type=int, default=10)
    demo.add_argument("--outage-length", type=int, default=16)
    demo.add_argument("--downlink-usd-per-mib", type=float, default=25.0)
    demo.add_argument("--inference-mj", type=float, default=12.0)
    check = sub.add_parser("verify", help="verify signatures, file integrity, replay, and assurance traceability")
    check.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "demo":
            report = make_bundle(
                args.output, count=args.records, seed=args.seed,
                threshold=args.threshold, queue_bytes=args.queue_bytes,
                outage_start=args.outage_start, outage_length=args.outage_length,
                downlink=args.downlink_usd_per_mib, energy=args.inference_mj,
            )
            verified = verify_bundle(args.output)
            result = {
                "output": str(args.output),
                "verified": verified["verified"],
                "records": report["records"],
                "authority_decision_counts": report["authority_decision_counts"],
                "signed_receipts_verified": report["signed_receipts_verified"],
                "decision": report["decision"],
            }
        else:
            check_result = verify_bundle(args.bundle)
            result = {k: v for k, v in check_result.items() if k != "report"}
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError, InvalidSignature) as error:
        parser.exit(1, f"verification failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
