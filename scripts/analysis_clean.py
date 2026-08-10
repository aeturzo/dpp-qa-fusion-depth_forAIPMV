#!/usr/bin/env python3
"""Re-report the results under stricter grading, and print what changes.

Three properties of the released grading affect the headline numbers. The paper
reports the figures as graded; this script quantifies what happens if you do not
accept that grading, so the effect is inspectable rather than something a reader
has to take on trust.

  P1  scope     173 of the 2,649 `logic` rows ask about the ontology's own
                vocabulary (`Is decimal a Datatype?`) or whether a bare
                measurement is a class instance (`Is 18 V a Thing?`). Neither is
                a product-passport question.
  P2  abstain   an explicit refusal is scored as a wrong answer.
  P3  leakage   a refusal that happens to contain the gold substring is scored
                as correct.

    $ python scripts/analysis_clean.py

Writes nothing; prints a report. Everything here is recomputed from
`data/verified/`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "data" / "verified"
SYSTEMS = ["longctx", "linc", "logiclm", "depth_aware"]
NAME = {"longctx": "LongCtx", "linc": "LINC", "logiclm": "LogicLM",
        "depth_aware": "depth-aware"}
KEY = ["id", "query"]


def out_of_scope(q: str) -> bool:
    return bool(re.search(r"a (?:Datatype|AnnotationProperty|Class)\?$", q)
                or re.match(r"^Is [0-9]", q))


def abstained(ans: str) -> bool:
    a = str(ans).strip()
    return (a.upper().startswith("INSUFFICIENT")
            or a.startswith("Premises:")
            or bool(re.match(r"^(cannot determine|not enough|unknown)", a, re.I)))


def subset(q: str) -> str:
    if re.search(r"a (?:Datatype|AnnotationProperty|Class)\?$", q):
        return "ontology vocabulary"
    if re.match(r"^Is [0-9]", q):
        return "bare measurement"
    return "product classification"


def table(title, rows, headers):
    w = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    print(f"\n{title}")
    print("  " + "  ".join(str(h).ljust(w[i]) for i, h in enumerate(headers)))
    print("  " + "  ".join("-" * w[i] for i in range(len(headers))))
    for r in rows:
        print("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))


def main() -> int:
    base = pd.read_csv(VER / "eval_depth_aware.csv")[KEY + ["type", "domain"]]
    m = base.copy()
    for s in SYSTEMS:
        d = pd.read_csv(VER / f"eval_{s}.csv")[KEY + ["correct", "answer"]]
        d = d.rename(columns={"correct": f"ok_{s}", "answer": f"ans_{s}"})
        m = m.merge(d, on=KEY, validate="one_to_one")
        m[f"ok_{s}"] = m[f"ok_{s}"].astype(bool)
        m[f"ab_{s}"] = m[f"ans_{s}"].map(abstained)
    m["oos"] = m["query"].map(out_of_scope)

    logic = m["type"] == "logic"
    print(f"rows {len(m):,} | logic {int(logic.sum()):,} | "
          f"out-of-scope logic {int((logic & m['oos']).sum())} "
          f"({100*(logic & m['oos']).sum()/logic.sum():.1f}% of logic)")

    g = m[logic].copy()
    g["sub"] = g["query"].map(subset)
    table("P1. accuracy within the logic type, by subset",
          [[k, f"{len(v):,}"] + [f"{100*v[f'ok_{s}'].mean():.2f}" for s in SYSTEMS]
           for k, v in g.groupby("sub")],
          ["subset", "n"] + [NAME[s] for s in SYSTEMS])

    table("P2. errors that are refusals rather than wrong answers",
          [[NAME[s], f"{int((~m[f'ok_{s}']).sum()):,}",
            f"{int((~m[f'ok_{s}'] & m[f'ab_{s}']).sum()):,}",
            f"{100*(~m[f'ok_{s}'] & m[f'ab_{s}']).sum()/max((~m[f'ok_{s}']).sum(),1):.0f}%",
            f"{int((~m[f'ok_{s}'] & ~m[f'ab_{s}']).sum()):,}"] for s in SYSTEMS],
          ["system", "errors", "refusals", "share", "substantive"])

    table("P3. refusals scored as correct",
          [[NAME[s], f"{int(m[f'ab_{s}'].sum()):,}",
            f"{int((m[f'ab_{s}'] & m[f'ok_{s}']).sum()):,}"] for s in SYSTEMS],
          ["system", "refusals", "scored correct"])

    for label, mask in (("A. as published", pd.Series(True, index=m.index)),
                        ("B. out-of-scope logic rows removed", ~m["oos"])):
        s_ = m[mask]
        table(f"{label}  (n={len(s_):,})",
              [[NAME[s]] + [f"{100*s_[s_['type']==t][f'ok_{s}'].mean():.2f}"
                            for t in ("recall", "open", "logic")]
               + [f"{100*s_[f'ok_{s}'].mean():.2f}"] for s in SYSTEMS],
              ["system", "recall", "open", "rule", "overall"])

    rows = []
    for label, mask in (("as published", pd.Series(True, index=m.index)),
                        ("out-of-scope removed", ~m["oos"])):
        s_, hs = m[mask], []
        for t in ("recall", "open", "logic"):
            v = s_[s_["type"] == t]
            best = max(v[f"ok_{s}"].mean() for s in SYSTEMS if s != "depth_aware")
            hs.append(100 * (v["ok_depth_aware"].mean() - best))
        rows.append([label] + [f"{h:.2f}" for h in hs]
                    + ["yes" if hs == sorted(hs) else "NO"])
    table("headroom to the ceiling", rows,
          ["view", "recall", "open", "rule", "rises with depth?"])

    rows = []
    for s in SYSTEMS[:3]:
        for label, mask in (("as published", pd.Series(True, index=m.index)),
                            ("out-of-scope removed", ~m["oos"])):
            v = m[mask]
            rows.append([NAME[s], label,
                         f"{int((v['ok_depth_aware'] & ~v[f'ok_{s}']).sum()):,}",
                         int((~v["ok_depth_aware"] & v[f"ok_{s}"]).sum())])
    table("paired disagreement (the zero column is the robust result)", rows,
          ["baseline", "view", "depth-aware only", "baseline only"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
