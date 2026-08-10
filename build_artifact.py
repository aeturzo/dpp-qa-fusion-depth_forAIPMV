#!/usr/bin/env python3
"""Build the public artifact repository from the locked results.

Creates ../dpp-qa-fusion-depth/ -- a self-contained folder intended to be
uploaded to GitHub and linked from the paper. It contains everything a reviewer
needs to recompute every number the paper reports, and nothing else.

WHAT IS REDACTED, AND WHY
-------------------------
The released per-question CSVs carry instrumentation columns that describe how
the system under study works. The paper defers the system description to a
separate publication, so those columns are dropped here rather than shipped:

    mode                    names the internal configuration
    steps                   full execution trace, including symbolic derivations
    n_steps, latency_ms     execution shape and timing
    confidence*             internal scoring, not used by any reported number
    cost_*                  call counts, token counts and spend
    success                 duplicate of `correct` under a different name

The columns that remain are exactly those the paper's numbers are computed
from. This is stated in the data card so a reviewer can see the boundary rather
than guess at it.

Nothing outside this script's output directory is written, and every source file
is opened read-only.

Usage:  python build_artifact.py
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCKED = REPO / "artifacts" / "locked_results" / "verified_v1_20260521_173612_CEST"
HANDOFF = REPO / "artifacts" / "paper_handoff_20260603"
OUT = HERE.parent / "dpp-qa-fusion-depth"

KEEP = ["id", "type", "domain", "product", "query", "expected_contains",
        "answer", "correct"]
DROP_REASON = {
    "mode": "names the internal configuration",
    "steps": "full execution trace including symbolic derivations",
    "n_steps": "execution shape",
    "latency_ms": "timing",
    "confidence": "internal scoring, unused by any reported number",
    "confidence_raw": "internal scoring",
    "confidence_cal": "internal scoring",
    "cost_retrieval_calls": "internal call counts",
    "cost_rule_checks": "internal call counts",
    "cost_tokens_in": "token accounting",
    "cost_tokens_out": "token accounting",
    "cost_usd_running": "spend",
    "success": "duplicate of `correct`",
    "session": "run-harness session label, unused by any reported number",
}

VERIFIED = {
    "longctx": "eval_GPT4O_LONGCTX_verified_v1.csv",
    "linc": "eval_LINC_verified_v1.csv",
    "logiclm": "eval_LOGIC_LM_verified_v1.csv",
    "depth_aware": "eval_ADAPTIVERAG_verified_v1_full.csv",
}

# The single compositional question quoted in Table II. The full compositional
# benchmark is not released here; only the row the paper shows.
EXAMPLE_ID = "arch-v2-002779"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    # Idempotent rather than destructive: files are overwritten in place, so a
    # rebuild never deletes anything a user may have added to the folder.
    for sub in ("data/verified", "data/public_schema", "data/examples",
                "scripts", "paper/figs"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    manifest = []

    # ---- verified subset, redacted ----
    for name, f in VERIFIED.items():
        d = pd.read_csv(LOCKED / f)
        missing = [c for c in KEEP if c not in d.columns]
        if missing:
            raise SystemExit(f"{f} is missing expected columns: {missing}")
        dropped = [c for c in d.columns if c not in KEEP]
        unexpected = [c for c in dropped if c not in DROP_REASON]
        if unexpected:
            raise SystemExit(
                f"{f} has columns with no documented redaction reason: "
                f"{unexpected}. Refusing to publish an undocumented drop.")
        p = OUT / "data/verified" / f"eval_{name}.csv"
        d[KEEP].to_csv(p, index=False)
        manifest.append((p, len(d), sorted(dropped)))

    e = pd.read_csv(LOCKED / "release_clean_verified_v1_exclusions.csv")
    p = OUT / "data/verified/exclusions.csv"
    e.to_csv(p, index=False)
    manifest.append((p, len(e), []))

    # ---- public-schema arm (summary level only; no architecture columns) ----
    for f in ("off_system_eval_summary.csv", "off_calibration_bins.csv",
              "off_ranked_risk_coverage.csv"):
        d = pd.read_csv(HANDOFF / f)
        p = OUT / "data/public_schema" / f.replace("off_", "")
        d.to_csv(p, index=False)
        manifest.append((p, len(d), []))

    # ---- the one compositional row quoted in Table II ----
    c = pd.read_csv(HANDOFF / "final_arch_3000_all3.csv")
    row = c[c["id"] == EXAMPLE_ID]
    if row.empty:
        raise SystemExit(f"example row {EXAMPLE_ID} not found")
    keep = ["id", "mode", "domain", "query", "expected_groups", "answer", "success"]
    row = row[keep].replace({"mode": {"AUTO_COMPOSE": "depth_aware",
                                      "GPT4O_LONGCTX": "longctx",
                                      "LOGIC_LM": "logiclm"}})
    p = OUT / "data/examples/table2_multisource.csv"
    row.to_csv(p, index=False)
    manifest.append((p, len(row), ["subtype (names an internal component)"]))

    # ---- paper outputs ----
    # The generator scripts (make_numbers.py, make_examples.py) are NOT shipped:
    # they read the private artifact tree and would fail for anyone who cloned
    # the repository. The repository instead ships their output together with
    # scripts/verify_all.py, which re-derives every one of those values from the
    # released CSVs and fails if the two disagree. That is a stronger guarantee
    # than shipping a script nobody can run.
    for f in ("numbers.tex", "tab_domain.tex", "tab_off.tex", "tab_examples.tex"):
        src = HERE / "paper" / f
        if src.exists():
            shutil.copy2(src, OUT / "paper" / f)
    fig = HERE / "paper" / "figs" / "by_type.pdf"
    if fig.exists():
        shutil.copy2(fig, OUT / "paper" / "figs" / "by_type.pdf")

    # ---- checksums ----
    lines = ["# Checksums", "",
             "SHA-256 of every data file in this repository.", "",
             "| file | rows | sha256 |", "|---|---|---|"]
    for p, n, _ in sorted(manifest, key=lambda t: str(t[0])):
        lines.append(f"| `{p.relative_to(OUT)}` | {n:,} | `{sha256(p)}` |")
    lines += ["", "## Columns withheld from the per-question files", "",
              "These describe how the system under study works and are deferred "
              "with the system description. No reported number depends on them.",
              "", "| column | reason |", "|---|---|"]
    for k, v in DROP_REASON.items():
        lines.append(f"| `{k}` | {v} |")
    (OUT / "CHECKSUMS.md").write_text("\n".join(lines) + "\n")

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built -> {OUT}  ({total/1e6:.1f} MB)")
    for p, n, dropped in manifest:
        d = f"  (dropped {len(dropped)})" if dropped else ""
        print(f"  {str(p.relative_to(OUT)):<44} {n:>6,} rows{d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
