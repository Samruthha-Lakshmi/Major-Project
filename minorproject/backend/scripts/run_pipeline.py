"""Run the pipeline from the command line (no server needed).

    python scripts/run_pipeline.py data/samples/student_performance.csv -o report.html
    python scripts/run_pipeline.py --live usgs -o quakes.html
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import ingest, runner  # noqa: E402
from app.sources import live  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="CSV / Excel / JSON dataset")
    ap.add_argument("--live", choices=[s["id"] for s in live.SOURCES], help="use a live source instead")
    ap.add_argument("--ai", action="store_true", help="use Claude for the narrative (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("-o", "--out", default="report.html")
    args = ap.parse_args()
    if not args.path and not args.live:
        ap.error("give a dataset path or --live SOURCE")

    if args.live:
        def loader(log):
            df, meta = live.fetch(args.live, {}, log)
            return ingest.finalize(df), meta
    else:
        p = Path(args.path)

        def loader(log):
            return ingest.load_bytes(p.name, p.read_bytes()), {"type": "upload", "name": p.name}

    t0 = time.perf_counter()

    def emit(e):
        if e["type"] == "stage" and e["status"] == "done":
            print(f"  ✓ {e['stage']:<10} {e['ms']:>6} ms")
        elif e["type"] == "log" and e["level"] != "info":
            print(f"  ! {e['message']}")

    result, html = runner.run("cli", loader, {"narrative_mode": "ai" if args.ai else "template",
                                               "alpha": args.alpha}, emit)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"\n{result['story']['headline']}\n{len(result['findings'])} findings · "
          f"{result['stats']['n_tests']} tests · {time.perf_counter() - t0:.1f}s → {args.out}")


if __name__ == "__main__":
    main()
