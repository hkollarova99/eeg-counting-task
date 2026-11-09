"""Distribution statistics for the generated trials.

Checks whether the start number, the end number (correct answer) and the seven
added steps are uniformly distributed, using a chi-square goodness-of-fit test.

Usage:
    python stats.py                     # simulate 1 session with config.py settings
    python stats.py --sessions 1000     # simulate many sessions (stable estimates)
    python stats.py --seed 42           # reproducible simulation
    python stats.py --csv data/*.csv    # analyse recorded sessions instead
    python stats.py --plot stats.png    # also save histograms
"""

from __future__ import annotations

import argparse
import csv
import glob
import random
from collections import Counter

from scipy.stats import chisquare

import design
from config import CONFIG, STRATEGIES


def simulate(sessions: int, seed: int | None) -> list[dict]:
    master = random.Random(seed)
    rows = []
    for _ in range(sessions):
        for t in design.build_session(CONFIG, master.randrange(2**32)):
            rows.append({"strategy": t.strategy, "start": t.start_value,
                         "end": t.correct_answer, "steps": list(t.steps)})
    return rows


def load_csv(patterns: list[str]) -> list[dict]:
    rows = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            with open(path, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    rows.append({"strategy": r["strategy"], "start": int(r["start_value"]),
                                 "end": int(r["correct_answer"]),
                                 "steps": [int(s) for s in r["steps"].split()]})
    return rows


def report(title: str, values: list[int], categories: list[int]) -> None:
    counts = Counter(values)
    observed = [counts.get(c, 0) for c in categories]
    n = sum(observed)
    expected = n / len(categories)
    print(f"\n{title}  (n={n}, uniform expectation = {expected:.1f} per value)")
    print(f"  {'value':>5} {'count':>7} {'%':>6}  {'obs/exp':>7}")
    for c, o in zip(categories, observed):
        bar = "#" * round(40 * o / max(observed)) if max(observed) else ""
        print(f"  {c:>5} {o:>7} {100 * o / n:>5.1f}%  {o / expected:>7.2f}  {bar}")
    stat, p = chisquare(observed)
    verdict = "NOT uniform" if p < 0.05 else "consistent with uniform"
    print(f"  chi2({len(categories) - 1}) = {stat:.2f}, p = {p:.3g}  ->  {verdict} (alpha 0.05)")
    if expected < 5:
        print("  (warning: expected counts < 5, the chi-square test is unreliable)")


def analyse(rows: list[dict], label: str) -> None:
    values = list(range(CONFIG.value_min, CONFIG.value_max + 1))
    steps = design.step_values(CONFIG)
    print(f"\n{'=' * 70}\n{label}: {len(rows)} trials\n{'=' * 70}")
    report("START number", [r["start"] for r in rows], values)
    report("END number (correct answer)", [r["end"] for r in rows], values)
    report("ALL STEPS pooled", [s for r in rows for s in r["steps"]], steps)
    for i in range(CONFIG.step_count):
        report(f"STEP {i + 1}", [r["steps"][i] for r in rows if len(r["steps"]) > i], steps)


def plot(rows: list[dict], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    values = list(range(CONFIG.value_min, CONFIG.value_max + 1))
    steps = design.step_values(CONFIG)
    panels = [("Start number", [r["start"] for r in rows], values),
              ("End number", [r["end"] for r in rows], values),
              ("All steps pooled", [s for r in rows for s in r["steps"]], steps)]
    panels += [(f"Step {i + 1}", [r["steps"][i] for r in rows], steps)
               for i in range(CONFIG.step_count)]
    cols = 4
    fig, axes = plt.subplots((len(panels) + cols - 1) // cols, cols,
                             figsize=(16, 3.2 * ((len(panels) + cols - 1) // cols)))
    for ax in axes.flat[len(panels):]:
        ax.axis("off")
    for ax, (title, data, cats) in zip(axes.flat, panels):
        counts = Counter(data)
        observed = [counts.get(c, 0) for c in cats]
        p = chisquare(observed).pvalue
        ax.bar(cats, observed, color="#4a7fb5")
        ax.axhline(len(data) / len(cats), color="#c0392b", linestyle="--",
                   linewidth=1.2, label="uniform")
        ax.set_title(f"{title}  (p = {p:.2g})", fontsize=10)
        ax.set_xticks(cats)
        ax.spines[["top", "right"]].set_visible(False)
    axes.flat[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Trial distributions, n = {len(rows)} trials "
                 "(dashed line = uniform expectation)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"\nPlot saved to {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", type=int, default=1,
                    help="number of simulated sessions (default 1)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--csv", nargs="+", help="analyse recorded CSV files instead")
    ap.add_argument("--by-strategy", action="store_true",
                    help="also report head and hands trials separately")
    ap.add_argument("--plot", metavar="PNG", help="save histograms to this file")
    args = ap.parse_args()

    rows = load_csv(args.csv) if args.csv else simulate(args.sessions, args.seed)
    if not rows:
        raise SystemExit("No trials found.")
    counts = Counter(r["strategy"] for r in rows)
    print("Trials per strategy: " + ", ".join(f"{s}={counts.get(s, 0)}" for s in STRATEGIES))

    analyse(rows, "ALL TRIALS")
    if args.by_strategy:
        for s in STRATEGIES:
            analyse([r for r in rows if r["strategy"] == s], f"STRATEGY = {s}")
    if args.plot:
        plot(rows, args.plot)


if __name__ == "__main__":
    main()
