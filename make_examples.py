#!/usr/bin/env python3
"""Generate paper/tab_examples.tex: one worked example per question class.

READ-ONLY over the locked artifacts. Rows 1-3 come from the verified subset;
row 4 comes from the separate compositional evaluation, which the table and its
caption state explicitly rather than blending the two.

Rows are pinned by (id, query) -- `id` alone is NOT unique in the verified CSVs
(449 duplicates) -- and the script aborts if a pinned row is missing or if a
recorded verdict stops matching the one the table is built to show, so it can
never emit a stale table.

Disclosure: the fused configuration appends the identifier of the record an
answer came from. That citation is stripped here for width, and the caption says
so. No other part of any answer is altered.

Usage:  python make_examples.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCKED = REPO / "artifacts" / "locked_results" / "verified_v1_20260521_173612_CEST"
COMPOSE = REPO / "artifacts" / "paper_handoff_20260603" / "final_arch_3000_all3.csv"
OUT = HERE / "paper" / "tab_examples.tex"

VERIFIED_FILES = {
    "LongCtx": "eval_GPT4O_LONGCTX_verified_v1.csv",
    "LINC": "eval_LINC_verified_v1.csv",
    "LogicLM": "eval_LOGIC_LM_verified_v1.csv",
    "Depth": "eval_ADAPTIVERAG_verified_v1_full.csv",
}
COMPOSE_MODES = {"LongCtx": "GPT4O_LONGCTX", "LogicLM": "LOGIC_LM",
                 "Depth": "AUTO_COMPOSE"}
COLS = ["LongCtx", "LINC", "LogicLM", "Depth"]

CASES = [
    {
        "src": "verified",
        "id": "cleandocrec-000022",
        "query": "According to viessmann_seed_0017, what is the Standard?",
        "label": "basic",
        "expect": {"LongCtx": True, "LINC": False, "LogicLM": True, "Depth": True},
        "verdict": "LINC swaps the declared field for a real regulation",
    },
    {
        "src": "verified",
        "id": "cleandocopen-000016",
        "query": "According to viessmann_seed_0002, what is the EU authorised representative?",
        "label": "open",
        "expect": {"LongCtx": True, "LINC": False, "LogicLM": True, "Depth": True},
        "verdict": "LINC answers from world knowledge, not from the record",
    },
    {
        "src": "verified",
        "id": "viessmann.kb.logic.01759",
        "query": "Is Gas a Thing?",
        "label": "reasoning",
        "expect": {"LongCtx": False, "LINC": True, "LogicLM": False, "Depth": True},
        "verdict": "both answer from plausibility rather than the schema",
    },
    {
        "src": "compose",
        "id": "arch-v2-002779",
        "label": "multi-source",
        "expect": {"LongCtx": False, "LogicLM": False, "Depth": True},
        "verdict": "each recovers two of three sources, then substitutes a real "
                   "but wrong standard",
        # This answer has three components and the systems differ on exactly one.
        # Showing it whole would truncate before the discriminating token, so the
        # cell is condensed to the three components. Every fragment below is
        # asserted to appear verbatim in the recorded answer before it is used,
        # and the emphasised index marks the component under dispute.
        "show": {
            "LongCtx": ["PrintPack", "UN 38.3", "separate collection symbol"],
            "LogicLM": ["PrintPack", "UN 38.3", "separate collection symbol"],
            "Depth": ["PrintPack", "RoHS", "separate collection symbol"],
        },
        "show_emph": 1,
    },
]

TEX = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
       "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def esc(s: str) -> str:
    s = str(s).replace("\\", r"\textbackslash{}")
    for k, v in TEX.items():
        s = s.replace(k, v)
    return (s.replace("°", r"\textdegree{}").replace("‑", "-")
             .replace("–", "--").replace("’", "'"))


def shorten(s: str, n: int) -> str:
    """Truncate at a word boundary so no cell ends mid-word."""
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:") + "…"


def strip_citation(s: str) -> str:
    """Drop the trailing [record] identifier the fused configuration appends."""
    return re.sub(r"\s*\[[^\]]*\]\s*\.?\s*$", "", str(s)).strip()


def gold_groups(raw: str) -> str:
    """Render expected_groups [[a],[b],[c]] as 'a | b | c'."""
    try:
        g = json.loads(raw)
        return " | ".join(str(x[0]) for x in g if x)
    except Exception:
        return str(raw)


def load_verified():
    return {n: pd.read_csv(LOCKED / f).set_index(["id", "query"])
            for n, f in VERIFIED_FILES.items()}


def main() -> int:
    ver = load_verified()
    comp = pd.read_csv(COMPOSE)

    rows = []
    for c in CASES:
        cells = {}
        if c["src"] == "verified":
            key = (c["id"], c["query"])
            gold, query = None, c["query"]
            for name in COLS:
                if key not in ver[name].index:
                    raise SystemExit(f"pinned row missing from {name}: {key}")
                r = ver[name].loc[key]
                if isinstance(r, pd.DataFrame):
                    raise SystemExit(f"(id,query) not unique in {name}: {key}")
                ok = bool(r["correct"])
                if ok != c["expect"][name]:
                    raise SystemExit(f"verdict changed for {key}/{name}: "
                                     f"artifact={ok} table assumes={c['expect'][name]}")
                cells[name] = (r["answer"], ok)
                gold = r["expected_contains"]
        else:
            s = comp[comp["id"] == c["id"]]
            if s.empty:
                raise SystemExit(f"compositional row missing: {c['id']}")
            query = s.iloc[0]["query"]
            gold = gold_groups(s.iloc[0]["expected_groups"])
            for name in COLS:
                if name not in COMPOSE_MODES:
                    cells[name] = (None, None)      # LINC was not run on this set
                    continue
                r = s[s["mode"] == COMPOSE_MODES[name]]
                if len(r) != 1:
                    raise SystemExit(f"expected 1 row for {name} in {c['id']}")
                r = r.iloc[0]
                ok = bool(r["success"])
                if ok != c["expect"][name]:
                    raise SystemExit(f"verdict changed for {c['id']}/{name}")
                cells[name] = (r["answer"], ok)
        rows.append((c, query, gold, cells))

    L = [
        r"% AUTO-GENERATED by make_examples.py -- do not edit by hand.",
        r"% Questions, gold values and answers are read from the released result files.",
        r"\begin{table*}[t]",
        r"\caption{One worked example per question class, quoted from the released "
        r"per-question outputs. A tick marks the recorded verdict; wrong answers "
        r"are set in italic. None of these failures is a fluency failure: every "
        r"wrong answer is well formed and plausible, and each substitutes the "
        r"system's own prior for what the record states. Answers in the "
        r"depth-aware column also carry the identifier of the record they were "
        r"drawn from, omitted here for width. The first three rows are from the "
        r"verified subset; the fourth is from a separate compositional "
        r"evaluation, on which LINC was not run. That answer has three "
        r"components and the systems differ on exactly one, shown in bold, so "
        r"the cell lists the three components rather than the full sentence.}",
        r"\label{tab:examples}",
        r"\centering\footnotesize",
        r"\setlength{\tabcolsep}{3.5pt}",
        # Never hyphenate inside a cell: the columns hold the values being
        # compared, and a break inside one makes them hard to read against
        # each other. With ragged right, words simply move to the next line.
        r"\hyphenpenalty=10000\exhyphenpenalty=10000",
        # Ragged right: these columns are too narrow for justified text, which
        # otherwise hyphenates across the values being compared. Written out per
        # column because a \newcommand is not a legal preamble token.
        r"\begin{tabular}{@{}"
        + "".join(rf">{{\raggedright\arraybackslash}}p{{{w}\textwidth}}"
                  for w in (0.228, 0.134, 0.104, 0.134, 0.134, 0.142))
        + r"@{}}",
        r"\toprule",
        r"question (gold in italics) & LongCtx & LINC & LogicLM & depth-aware & "
        r"verdict \\",
        r"\midrule",
    ]
    for c, query, gold, cells in rows:
        q = (f"\\textbf{{{c['label']}}}\\newline {esc(shorten(query, 116))}"
             f"\\newline \\textit{{{esc(shorten(gold, 52))}}}")
        out = [q]
        for name in COLS:
            ans, ok = cells[name]
            if ok is None:
                out.append(r"\textit{not run}")
                continue
            if "show" in c and name in c["show"]:
                parts = []
                for j, frag in enumerate(c["show"][name]):
                    if frag not in str(ans):
                        raise SystemExit(
                            f"fragment {frag!r} is not a literal substring of the "
                            f"recorded {name} answer for {c['id']}; refusing to "
                            f"print a condensation that is not in the artifact.")
                    e = esc(frag)
                    parts.append(rf"\textbf{{{e}}}" if j == c.get("show_emph")
                                 else e)
                # Breakable spaces around the separator: a non-breaking one here
                # makes the whole list unbreakable and overflows the column.
                body = r" $\cdot$ ".join(parts)
            else:
                body = esc(shorten(strip_citation(ans), 46))
            out.append((r"\checkmark~" + body) if ok
                       else (r"$\times$~\emph{" + body + "}"))
        out.append(esc(c["verdict"]))
        L.append(" & ".join(out) + r" \\[3pt]")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n")
    print(f"written -> {OUT}\n")
    for c, query, gold, cells in rows:
        print(f"[{c['label']}] {shorten(query, 96)}\n  gold: {shorten(gold, 80)}")
        for name in COLS:
            a, ok = cells[name]
            mark = "--- " if ok is None else ("OK  " if ok else "WRONG")
            print(f"    {name:8} {mark} "
                  f"{'not run' if a is None else shorten(strip_citation(a), 76)}")
        print(f"  verdict: {c['verdict']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
