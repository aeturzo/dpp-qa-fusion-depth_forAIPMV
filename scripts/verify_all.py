#!/usr/bin/env python3
"""Recompute every number the paper reports and check it against the paper.

This is a cross-check, not a recomputation. The claimed values are parsed out of
`paper/numbers.tex` -- the macro file the paper itself is typeset from -- and
compared against values recomputed here from the released CSVs. If the paper and
the data ever disagree, this fails and says where.

    $ python scripts/verify_all.py
    ...
    62 checks, 62 passed, 0 failed

Exit status is 0 only if every check passes, so it can be used in CI.

A note on joining: `id` is NOT unique in these files (449 ids appear twice, on
different products), and the four files are not in the same row order. Anything
that pairs systems question-by-question must join on `(id, query)`. Using `id`
alone silently produces a cartesian product.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "data" / "verified"
PUB = ROOT / "data" / "public_schema"
EX = ROOT / "data" / "examples"
MACROS = ROOT / "paper" / "numbers.tex"

SYSTEMS = ["longctx", "linc", "logiclm", "depth_aware"]
LABEL = {"longctx": "LongCtx", "linc": "LINC", "logiclm": "LogicLM",
         "depth_aware": "Sys"}
KEY = ["id", "query"]

results: list[tuple[bool, str, str, str]] = []


def check(name: str, got, want, tol: float = 0.005) -> None:
    """Compare a recomputed value against the paper's claim.

    Numeric comparison whenever both sides can be read as numbers; LaTeX thin
    separators (``6{,}270``) are stripped first. Falls back to exact string
    equality, which is what the domain-name and boolean checks want.
    """
    def as_number(v):
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(str(v).replace("{,}", "").replace(",", ""))
        except ValueError:
            return None

    g, w = as_number(got), as_number(want)
    ok = abs(g - w) <= tol if (g is not None and w is not None) \
        else str(got) == str(want)
    results.append((ok, name, str(got), str(want)))


def load_macros() -> dict[str, str]:
    """Parse \\newcommand definitions, one per line.

    Values may themselves contain braces (``6{,}270``), so the value is taken as
    everything between the first ``{`` after the name and the final ``}`` on the
    line rather than by a non-greedy character class.
    """
    if not MACROS.exists():
        sys.exit(f"missing {MACROS}; run scripts/make_numbers.py first")
    out = {}
    for line in MACROS.read_text().splitlines():
        mm = re.match(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}\s*$", line)
        if mm:
            out[mm.group(1)] = mm.group(2)
    if not out:
        sys.exit(f"no macros parsed from {MACROS}")
    return out


def mcnemar_p(n01: int, n10: int) -> float:
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main() -> int:
    m = load_macros()
    f = {s: pd.read_csv(VER / f"eval_{s}.csv") for s in SYSTEMS}

    # ---------- integrity of the release itself ----------
    base = f["depth_aware"]
    check("row count", len(base), m["VerifiedN"], 0)
    check("domains", base["domain"].nunique(), m["VerifiedDomains"], 0)
    for s in SYSTEMS:
        check(f"{s}: same row count", len(f[s]), len(base), 0)
        dup = f[s].duplicated(KEY).sum()
        check(f"{s}: (id,query) is unique", dup, 0, 0)
    keys = {s: set(map(tuple, f[s][KEY].values)) for s in SYSTEMS}
    for s in SYSTEMS[1:]:
        check(f"{s}: same question set as depth_aware",
              keys[s] == keys["depth_aware"], True, 0)

    # ---------- accuracy, overall and by question class ----------
    for s in SYSTEMS:
        d = f[s]
        check(f"{LABEL[s]} overall accuracy",
              100 * d["correct"].astype(bool).mean(), m[f"Acc{LABEL[s]}"])
        check(f"{LABEL[s]} errors",
              int((~d["correct"].astype(bool)).sum()), m[f"Err{LABEL[s]}"], 0)
        for t in ("recall", "open", "logic"):
            sub = d[d["type"] == t]
            check(f"{LABEL[s]} {t} accuracy",
                  100 * sub["correct"].astype(bool).mean(),
                  m[f"Acc{LABEL[s]}{t.capitalize()}"])

    # ---------- headroom to the ceiling ----------
    for t in ("recall", "open", "logic"):
        best = max(100 * f[s][f[s]["type"] == t]["correct"].astype(bool).mean()
                   for s in SYSTEMS if s != "depth_aware")
        ceil = 100 * f["depth_aware"][f["depth_aware"]["type"] == t][
            "correct"].astype(bool).mean()
        check(f"headroom {t}", ceil - best, m[f"Headroom{t.capitalize()}"])

    # ---------- paired discordance (joined on the composite key) ----------
    sysd = f["depth_aware"].set_index(KEY)["correct"].astype(bool)
    for s in SYSTEMS[:3]:
        b = f[s].set_index(KEY)["correct"].astype(bool)
        common = sysd.index.intersection(b.index)
        check(f"{LABEL[s]}: join is lossless", len(common), len(base), 0)
        a, bb = sysd.loc[common], b.loc[common]
        n01, n10 = int((a & ~bb).sum()), int((~a & bb).sum())
        check(f"{LABEL[s]} system-only correct", n01, m[f"Disc{LABEL[s]}SysOnly"], 0)
        check(f"{LABEL[s]} baseline-only correct", n10,
              m[f"Disc{LABEL[s]}BaseOnly"], 0)
        exp = int(math.floor(-math.log10(mcnemar_p(n01, n10))))
        check(f"{LABEL[s]} McNemar p < 1e-{m['McnExp']}",
              exp >= int(m["McnExp"]), True, 0)

    # ---------- exclusions ----------
    e = pd.read_csv(VER / "exclusions.csv")
    check("excluded rows", len(e), m["ExcludedRows"], 0)
    check("exclusion reasons", e["reason"].nunique(), m["ExcludedReasons"], 0)
    # Must be checked on the composite key. 154 excluded ids also occur in the
    # scored set, but they are different questions that happen to share an id --
    # on (id, query) the two sets are disjoint, which is the property that
    # matters: no excluded question was scored.
    ex_keys = set(map(tuple, e[KEY].values))
    base_keys = set(map(tuple, base[KEY].values))
    check("exclusions disjoint from the scored set (id, query)",
          len(ex_keys & base_keys), 0, 0)

    # ---------- domain ordering ----------
    share = base.groupby("domain")["type"].apply(lambda s: (s == "logic").mean())
    order = list(share.sort_values(ascending=False).index)
    check("domain with most schema-governed questions", order[0], m["DomainMostRule"], 0)
    check("domain with fewest", order[-1], m["DomainLeastRule"], 0)
    lc = f["longctx"].groupby("domain")["correct"].apply(lambda s: s.astype(bool).mean())
    check("baseline accuracy falls as rule share rises",
          list(lc[order]) == sorted(lc[order]), True, 0)

    # ---------- public-schema arm ----------
    off = pd.read_csv(PUB / "system_eval_summary.csv")
    a = off[off["query_type"] == "ALL"].iloc[0]
    check("public-schema n", int(a["n"]), m["OffN"], 0)
    check("public-schema accuracy", 100 * a["accuracy"], m["OffAcc"])
    check("public-schema coverage", 100 * a["answer_coverage"], m["OffCoverage"], 0.05)
    check("public-schema ECE", a["ece_10bin"], float(m["OffEce"]), 0.0005)
    check("public-schema AURC", a["aurc"], float(m["OffAurc"]), 0.0005)
    check("abstain precision", a["abstain_precision"], float(m["OffAbstainPrec"]), 0.0005)
    check("abstain recall", a["abstain_recall"], float(m["OffAbstainRec"]), 0.0005)

    # ---------- Table II examples ----------
    tab2 = [
        ("cleandocrec-000022", "According to viessmann_seed_0017, what is the Standard?",
         {"longctx": 1, "linc": 0, "logiclm": 1, "depth_aware": 1}),
        ("cleandocopen-000016",
         "According to viessmann_seed_0002, what is the EU authorised representative?",
         {"longctx": 1, "linc": 0, "logiclm": 1, "depth_aware": 1}),
        ("viessmann.kb.logic.01759", "Is Gas a Thing?",
         {"longctx": 0, "linc": 1, "logiclm": 0, "depth_aware": 1}),
    ]
    for qid, q, want in tab2:
        for s, w in want.items():
            r = f[s][(f[s]["id"] == qid) & (f[s]["query"] == q)]
            check(f"Table II [{qid[:22]}] {LABEL[s]}",
                  int(r.iloc[0]["correct"]) if len(r) == 1 else "missing", w, 0)

    ex = pd.read_csv(EX / "table2_multisource.csv")
    for mode, w in (("longctx", 0), ("logiclm", 0), ("depth_aware", 1)):
        r = ex[ex["mode"] == mode]
        check(f"Table II [multi-source] {mode}",
              int(r.iloc[0]["success"]) if len(r) == 1 else "missing", w, 0)
    check("Table II [multi-source] LINC absent", (ex["mode"] == "linc").sum(), 0, 0)

    # ---------- report ----------
    width = max(len(n) for _, n, _, _ in results)
    failed = [r for r in results if not r[0]]
    for ok, name, got, want in results:
        if not ok:
            print(f"FAIL  {name:<{width}}  recomputed={got}  paper={want}")
    print(f"\n{len(results)} checks, {len(results)-len(failed)} passed, "
          f"{len(failed)} failed")
    if not failed:
        print("Every number in the paper matches the released data.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
