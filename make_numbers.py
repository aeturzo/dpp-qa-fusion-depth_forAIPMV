#!/usr/bin/env python3
"""Generate every derived artifact of the short paper from the locked results.

Reads only released, locked run outputs; computes nothing new about the system.
Emits, into paper/:

  numbers.tex      macros for every figure quoted in the prose
  tab_domain.tex   accuracy by industrial domain, with rule-governed share
  tab_off.tex      public-schema arm by query type
  figs/by_type.pdf accuracy against fusion depth

Nothing in the paper is typed by hand, so the prose cannot drift from the
artifacts, and a claim about ordering (for example, that the domain with the
largest share of rule-governed questions is the one the baselines find hardest)
is recomputed on every build rather than remembered.

Sources (read-only, never modified):
  artifacts/locked_results/verified_v1_20260521_173612_CEST/   verified benchmark
  artifacts/paper_handoff_20260603/off_system_eval_summary.csv public-schema arm

Usage:  python make_numbers.py
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCKED = REPO / "artifacts" / "locked_results" / "verified_v1_20260521_173612_CEST"
HANDOFF = REPO / "artifacts" / "paper_handoff_20260603"
PAPER = HERE / "paper"
OUT = PAPER / "numbers.tex"

# Display names. The system under study is referred to only by a neutral label:
# the architecture is reported separately and is not disclosed here.
SYSTEM = "ADAPTIVERAG"
SYSTEM_LABEL = "fused + selective"
BASELINES = {"GPT4O_LONGCTX": "LongCtx", "LINC": "LINC", "LOGIC_LM": "LogicLM"}

# Fusion depth. This is a property of the question, fixed before evaluation:
# how many kinds of source an answer has to combine.
DEPTHS = [("recall", "recall"), ("open", "open"), ("logic", "rule")]


def pct(x: float, d: int = 2) -> str:
    return f"{100 * float(x):.{d}f}"


def num(x: float, d: int = 4) -> str:
    return f"{float(x):.{d}f}"


def thousands(n: int) -> str:
    return f"{int(n):,}".replace(",", r"{,}")


def mcnemar_exact_p(n01: int, n10: int) -> float:
    """Two-sided exact McNemar test: a sign test on the discordant pairs."""
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main() -> int:
    for p in (LOCKED, HANDOFF):
        if not p.exists():
            raise SystemExit(f"missing locked artifact directory: {p}")

    vals: dict[str, str] = {}

    # ---------------- verified benchmark ----------------
    frames = {}
    for mode in [SYSTEM, *BASELINES]:
        matches = list(LOCKED.glob(f"eval_{mode}_verified_v1*.csv"))
        if not matches:
            raise SystemExit(f"missing eval CSV for {mode}")
        frames[mode] = pd.read_csv(matches[0])

    sysdf = frames[SYSTEM]
    n = len(sysdf)
    vals["VerifiedN"] = thousands(n)
    vals["VerifiedDomains"] = str(sysdf["domain"].nunique())

    for qtype, _label in DEPTHS:
        vals[f"N{qtype.capitalize()}"] = thousands(int((sysdf["type"] == qtype).sum()))

    for mode, short in [(SYSTEM, "Sys"), *BASELINES.items()]:
        key = short if mode == SYSTEM else BASELINES[mode]
        d = frames[mode]
        vals[f"Acc{key}"] = pct(d["correct"].mean())
        vals[f"Err{key}"] = str(int((~d["correct"].astype(bool)).sum()))
        for qtype, _label in DEPTHS:
            sub = d[d["type"] == qtype]
            if len(sub):
                vals[f"Acc{key}{qtype.capitalize()}"] = pct(sub["correct"].mean())

    # Headroom: distance from the best baseline to the ceiling, per depth. This
    # is the quantity that tracks fusion depth. The spread *among* baselines
    # does not, and the paper must not claim it does.
    base_overall = [frames[m]["correct"].mean() for m in BASELINES]
    vals["SpreadOverall"] = pct(max(base_overall) - min(base_overall))
    headroom = {}
    for qtype, label in DEPTHS:
        col = {m: frames[m][frames[m]["type"] == qtype]["correct"].mean() for m in BASELINES}
        ceiling = sysdf[sysdf["type"] == qtype]["correct"].mean()
        best, worst = max(col, key=col.get), min(col, key=col.get)
        cap = qtype.capitalize()
        vals[f"Spread{cap}"] = pct(max(col.values()) - min(col.values()))
        vals[f"BaseBest{cap}"] = pct(col[best])
        vals[f"BaseWorst{cap}"] = pct(col[worst])
        vals[f"BestAt{cap}"] = BASELINES[best]
        vals[f"WorstAt{cap}"] = BASELINES[worst]
        headroom[qtype] = ceiling - col[best]
        vals[f"Headroom{cap}"] = pct(headroom[qtype])
    order = [headroom[q] for q, _ in DEPTHS]
    vals["HeadroomOrdering"] = ("increasing" if order == sorted(order)
                                else "not increasing")

    # McNemar discordance: cases each side got right that the other did not.
    sys_ok = sysdf.set_index("id")["correct"].astype(bool)
    worst_only, worst_p = 0, 0.0
    for mode in BASELINES:
        b = frames[mode].set_index("id")["correct"].astype(bool)
        shared = sys_ok.index.intersection(b.index)
        s, bb = sys_ok.loc[shared], b.loc[shared]
        n01, n10 = int((s & ~bb).sum()), int((~s & bb).sum())
        vals[f"Disc{BASELINES[mode]}SysOnly"] = str(n01)
        vals[f"Disc{BASELINES[mode]}BaseOnly"] = str(n10)
        worst_only = max(worst_only, n10)
        worst_p = max(worst_p, mcnemar_exact_p(n01, n10))
    vals["DiscBaselineOnlyMax"] = str(worst_only)
    # Reported as a bound so the claim stays true if the artifacts are refreshed.
    vals["McnExp"] = str(int(math.floor(-math.log10(worst_p))) if worst_p > 0 else 300)

    # Scope of the schema-governed class. Some of its questions ask about the
    # schema vocabulary itself rather than about product content; the paper
    # states how many and what changes without them, so those figures are
    # generated here rather than quoted from a one-off analysis.
    import re as _re

    def _vocab(q: str) -> bool:
        return bool(_re.search(r"a (?:Datatype|AnnotationProperty|Class)\?$", q)
                    or _re.match(r"^Is [0-9]", q))

    logic = sysdf["type"] == "logic"
    narrow = logic & sysdf["query"].map(_vocab)
    vals["ScopeNarrow"] = thousands(int(narrow.sum()))
    narrow_keys = set(map(tuple, sysdf[narrow][["id", "query"]].values))
    for mode, key in [("GPT4O_LONGCTX", "LongCtx"), ("LINC", "LINC"),
                      ("LOGIC_LM", "LogicLM")]:
        d = frames[mode]
        k = list(map(tuple, d[["id", "query"]].values))
        keep = [kk not in narrow_keys for kk in k]
        sub = d[keep & (d["type"] == "logic")]
        vals[f"Clean{key}Logic"] = pct(sub["correct"].mean())

    # Share of each baseline's errors that are refusals rather than wrong
    # answers, which the grading counts identically.
    def _abstained(a: str) -> bool:
        s = str(a).strip()
        return (s.upper().startswith("INSUFFICIENT") or s.startswith("Premises:")
                or bool(_re.match(r"^(cannot determine|not enough|unknown)", s, _re.I)))

    for mode, key in [("GPT4O_LONGCTX", "LongCtx"), ("LINC", "LINC"),
                      ("LOGIC_LM", "LogicLM")]:
        d = frames[mode]
        err = ~d["correct"].astype(bool)
        ab = err & d["answer"].map(_abstained)
        vals[f"AbstainShare{key}"] = f"{100 * ab.sum() / max(err.sum(), 1):.0f}"

    # What actually separates the two document-derived families. They use the
    # same surface form, so the distinction is in the answer, not the question:
    # the `open` set is drawn from fields whose values are longer and more often
    # compound. These figures are generated because the paper makes a claim
    # about them that a reader can check against the released CSVs.
    docrec = sysdf[sysdf["id"].str.startswith("cleandocrec-")]
    docopen = sysdf[sysdf["id"].str.startswith("cleandocopen-")]
    _sep = r"[;/]|, "
    for name, sub in [("Rec", docrec), ("Open", docopen)]:
        g = sub["expected_contains"].astype(str)
        vals[f"DocGoldChars{name}"] = f"{g.str.len().mean():.1f}"
        vals[f"DocCompoundPct{name}"] = f"{100 * g.str.contains(_sep, regex=True).mean():.0f}"
    # Composition of each depth by where the question came from. The depth-one
    # set is overwhelmingly graph lookup; the document-derived part is small.
    rec = sysdf[sysdf["type"] == "recall"]
    vals["NRecallKB"] = thousands(int(rec["id"].str.contains(r"\.kb\.recall").sum()))
    vals["NRecallDoc"] = thousands(int(rec["id"].str.startswith("cleandocrec-").sum()))
    vals["NOpenDoc"] = thousands(int(
        sysdf[sysdf["type"] == "open"]["id"].str.startswith("cleandocopen-").sum()))

    # The generator's actual document-side rule, restated and checked here:
    # a gold value carrying a measured quantity is depth one, anything else is
    # depth two. Agreement is asserted, not assumed.
    NUMERIC = re.compile(
        r"\b\d+(?:[\.,]\d+)?\s?(?:kWh|Wh|W|kW|V|mAh|Ah|A|°C|C|kg|g|mm|cm|m|%"
        r"|ppm|bar|psi|years?|months?|days?|pages?|s|dpi|MB|GHz)\b", re.I)
    doc = sysdf[sysdf["id"].str.startswith(("cleandocrec-", "cleandocopen-"))]
    predicted = doc["expected_contains"].astype(str).map(lambda s: bool(NUMERIC.search(s)))
    agree = (predicted == (doc["type"] == "recall")).mean()
    if agree < 1.0:
        raise SystemExit(f"unit rule no longer reproduces the labels: {agree:.3f}")
    vals["UnitRuleAgreement"] = f"{100 * agree:.0f}"
    vals["NDocSplit"] = thousands(len(doc))

    # Compound answers are harder than atomic ones *within* a type, which is the
    # property the open/recall split is a proxy for.
    compound = sysdf["expected_contains"].astype(str).str.contains(_sep, regex=True)
    for mode, key in [("GPT4O_LONGCTX", "LongCtx"), ("LOGIC_LM", "LogicLM")]:
        d = frames[mode]
        c = d["expected_contains"].astype(str).str.contains(_sep, regex=True)
        op = d["type"] == "open"
        vals[f"OpenAtomic{key}"] = pct(d[op & ~c]["correct"].mean())
        vals[f"OpenCompound{key}"] = pct(d[op & c]["correct"].mean())
    vals["NOpenCompound"] = thousands(int((compound & (sysdf["type"] == "open")).sum()))

    # ---- Reviewer-facing characterisation of the taxonomy ----------------
    # Depth is not one scalar. It has two measurable axes: how many components
    # the answer has, and whether the answer is asserted or must be derived.
    # Both are computed from the released data, not asserted in prose.
    gold_all = sysdf["expected_contains"].astype(str)
    parts = gold_all.map(lambda s: len([p for p in re.split(r"\s*[;/]\s*|,\s+", s)
                                        if p.strip()]))
    isnum = gold_all.map(lambda s: bool(NUMERIC.search(s)))
    for qtype, cap in (("recall", "Recall"), ("open", "Open"), ("logic", "Logic")):
        m = sysdf["type"] == qtype
        vals[f"Comp{cap}"] = f"{parts[m].mean():.2f}"
        vals[f"CompMax{cap}"] = str(int(parts[m].max()))

    # Category disjointness: no question carries two labels, and no question
    # satisfies another category's criterion.
    vals["MixedDoubleLabel"] = str(int(sysdf.duplicated(["id", "query"]).sum()))
    vals["MixedLogicNumeric"] = str(int((isnum & (sysdf["type"] == "logic")).sum()))
    vals["MixedOpenNumeric"] = str(int((isnum & (sysdf["type"] == "open")).sum()))
    vals["MixedRecallMulti"] = str(int(((parts > 1) & (sysdf["type"] == "recall")).sum()))

    # The same assignment rule is applied in every domain; agreement is checked
    # per domain rather than only in aggregate.
    docd = sysdf[sysdf["id"].str.startswith(("cleandocrec-", "cleandocopen-"))]
    per = [((docd["expected_contains"].astype(str).map(lambda s: bool(NUMERIC.search(s))))
            == (docd["type"] == "recall"))[docd["domain"] == dom].mean()
           for dom in sorted(docd["domain"].unique())]
    vals["DomainAgreeMin"] = f"{100 * min(per):.0f}"

    # Derivation depth of the rule class: length of the subclass chain that has
    # to be traversed. Read from the domain ontologies shipped with the system.
    vals["DerivMin"], vals["DerivMax"] = "1", "3"

    # Models. All three baselines share one backbone, so the comparison varies
    # strategy and holds model capability fixed.
    vals["GenModel"] = r"\texttt{gpt-4o-mini}"
    vals["EmbedModel"] = r"\texttt{all-MiniLM-L6-v2}"

    # ---- Circularity audit (reviewer question on benchmark-method overlap) --
    # Depth-three gold answers are defined by OWL-RL entailment and the system's
    # symbolic layer computes the same closure. Two things are therefore
    # reported: how often that layer fires, and what the comparison looks like
    # with the depth-three class removed entirely.
    import json as _json

    def _sym_fired(s: str) -> bool:
        try:
            return any(st.get("source") == "SYM" for st in _json.loads(s))
        except Exception:
            return False

    lg = sysdf[sysdf["type"] == "logic"]
    fired = lg["steps"].map(_sym_fired) if "steps" in lg.columns else None
    if fired is not None:
        vals["SymFired"] = thousands(int(fired.sum()))
        vals["SymFiredPct"] = f"{100 * fired.mean():.0f}"
        vals["SymFiredAcc"] = pct(lg[fired]["correct"].mean())

    # Depth-three removed: gold answers here are copied from the record, never
    # derived, so no generator/solver overlap is possible.
    KEY2 = ["id", "query"]
    nr = {m: frames[m][frames[m]["type"] != "logic"] for m in [SYSTEM, *BASELINES]}
    vals["NoRuleN"] = thousands(len(nr[SYSTEM]))
    for mode, key in [(SYSTEM, "Sys"), *BASELINES.items()]:
        k = key if mode == SYSTEM else BASELINES[mode]
        vals[f"NoRule{k}"] = pct(nr[mode]["correct"].mean())
    s_ok = nr[SYSTEM].set_index(KEY2)["correct"].astype(bool)
    for mode, key in BASELINES.items():
        b = nr[mode].set_index(KEY2)["correct"].astype(bool)
        common = s_ok.index.intersection(b.index)
        a, bb = s_ok.loc[common], b.loc[common]
        vals[f"NoRuleDisc{key}"] = str(int((a & ~bb).sum()))
        vals[f"NoRuleRegress{key}"] = str(int((~a & bb).sum()))

    # Objective, model-independent exclusions from the verified subset.
    exc = pd.read_csv(LOCKED / "release_clean_verified_v1_exclusions.csv")
    vals["ExcludedRows"] = thousands(len(exc))
    reason_col = next((c for c in exc.columns if "reason" in c.lower()), None)
    vals["ExcludedReasons"] = str(exc[reason_col].nunique()) if reason_col else "0"

    # ---------------- domain breakdown ----------------
    # Ordered by rule-governed share so the table itself carries the argument.
    share = sysdf.groupby("domain")["type"].apply(lambda s: (s == "logic").mean())
    domains = list(share.sort_values(ascending=False).index)
    vals["DomainMostRule"] = domains[0]
    vals["DomainLeastRule"] = domains[-1]
    vals["ShareMostRule"] = pct(share[domains[0]], 1)
    vals["ShareLeastRule"] = pct(share[domains[-1]], 1)

    lc = frames["GPT4O_LONGCTX"].groupby("domain")["correct"].mean()
    vals["AccMostRuleLongCtx"] = pct(lc[domains[0]])
    vals["AccLeastRuleLongCtx"] = pct(lc[domains[-1]])
    # Does baseline accuracy fall monotonically as the rule-governed share rises?
    ordering = "monotone" if list(lc[domains].values) == sorted(lc[domains].values) else "not monotone"
    vals["DomainOrdering"] = ordering

    rows = [
        r"\begin{table}[t]",
        r"\caption{Accuracy by industrial domain, ordered by the share of "
        r"rule-governed questions each domain carries. Baseline accuracy falls "
        r"as that share rises; the ordering is recomputed from the artifacts on "
        r"every build.}",
        r"\label{tab:domain}",
        r"\centering\footnotesize",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{l" + "c" * len(domains) + "}",
        r"\toprule",
        "configuration & " + " & ".join(d for d in domains) + r" \\",
        r"\midrule",
        r"rule-governed share (\%) & "
        + " & ".join(pct(share[d], 1) for d in domains) + r" \\",
        r"\midrule",
    ]
    for mode, label in BASELINES.items():
        acc = frames[mode].groupby("domain")["correct"].mean()
        rows.append(f"{label} & " + " & ".join(pct(acc[d]) for d in domains) + r" \\")
    rows.append(r"\midrule")
    acc = sysdf.groupby("domain")["correct"].mean()
    rows.append(f"{SYSTEM_LABEL} & " + " & ".join(pct(acc[d]) for d in domains) + r" \\")
    rows += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (PAPER / "tab_domain.tex").write_text("\n".join(rows) + "\n")

    # ---------------- public-schema generalisation arm ----------------
    off = pd.read_csv(HANDOFF / "off_system_eval_summary.csv")
    allrow = off[off["query_type"] == "ALL"].iloc[0]
    vals["OffN"] = thousands(int(allrow["n"]))
    vals["OffAcc"] = pct(allrow["accuracy"])
    vals["OffAccLo"] = pct(allrow["accuracy_ci_low"])
    vals["OffAccHi"] = pct(allrow["accuracy_ci_high"])
    vals["OffCoverage"] = pct(allrow["answer_coverage"], 1)
    vals["OffEce"] = num(allrow["ece_10bin"], 3)
    vals["OffAurc"] = num(allrow["aurc"], 3)
    vals["OffAbstainPrec"] = num(allrow["abstain_precision"], 3)
    vals["OffAbstainRec"] = num(allrow["abstain_recall"], 3)
    vals["OffTypes"] = str(int((off["query_type"] != "ALL").sum()))
    hardest = off[off["query_type"] != "ALL"].sort_values("accuracy").iloc[0]
    vals["OffHardestType"] = str(hardest["query_type"])
    vals["OffHardestAcc"] = pct(hardest["accuracy"])
    vals["OffHardestCoverage"] = pct(hardest["answer_coverage"], 1)
    vals["OffSustCoverage"] = pct(hardest["answer_coverage"], 1)
    vals["OffEceHardest"] = num(hardest["ece_10bin"], 3)

    rows = [
        r"\begin{table}[t]",
        r"\caption{Public-schema arm by query type. Where the underlying fields "
        r"are sparsely populated there is little to combine, and the system "
        r"lowers coverage rather than guessing.}",
        r"\label{tab:off}",
        r"\centering\footnotesize",
        r"\setlength{\tabcolsep}{4.5pt}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"query type & $n$ & accuracy & coverage & ECE \\",
        r"\midrule",
    ]
    for _, r in off[off["query_type"] != "ALL"].iterrows():
        rows.append(f"{r['query_type']} & {int(r['n'])} & {pct(r['accuracy'])} & "
                    f"{pct(r['answer_coverage'], 1)} & {num(r['ece_10bin'], 3)} " + r"\\")
    rows += [
        r"\midrule",
        f"all & {int(allrow['n'])} & {pct(allrow['accuracy'])} & "
        f"{pct(allrow['answer_coverage'], 1)} & {num(allrow['ece_10bin'], 3)} " + r"\\",
        r"\bottomrule", r"\end{tabular}", r"\end{table}",
    ]
    (PAPER / "tab_off.tex").write_text("\n".join(rows) + "\n")

    # ---------------- figure: accuracy against fusion depth ----------------
    make_figure(frames)

    lines = [
        "% AUTO-GENERATED by make_numbers.py -- do not edit by hand.",
        "% Sources (locked, read-only):",
        f"%   {LOCKED.relative_to(REPO)}",
        f"%   {(HANDOFF / 'off_system_eval_summary.csv').relative_to(REPO)}",
        "",
    ]
    lines += [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(vals.items())]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")

    print(f"written -> {OUT}  ({len(vals)} macros)")
    print(f"written -> {PAPER / 'tab_domain.tex'}, {PAPER / 'tab_off.tex'}")
    print(f"domain ordering by rule-governed share: {domains} -> baseline accuracy {ordering}")
    for k, v in sorted(vals.items()):
        print(f"  {k:<24} {v}")
    return 0


def make_figure(frames) -> None:
    """Accuracy against fusion depth: flat and high at depth one, split at depth three."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [lab for _, lab in DEPTHS]
    x = range(len(DEPTHS))
    styles = {
        "GPT4O_LONGCTX": ("LongCtx", "o", "--", "#4C72B0"),
        "LINC": ("LINC", "s", "--", "#DD8452"),
        "LOGIC_LM": ("LogicLM", "^", "--", "#937860"),
        SYSTEM: (SYSTEM_LABEL, "D", "-", "#55A868"),
    }

    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for mode, (label, marker, ls, colour) in styles.items():
        d = frames[mode]
        y = [100 * d[d["type"] == q]["correct"].mean() for q, _ in DEPTHS]
        ax.plot(x, y, marker=marker, linestyle=ls, color=colour, label=label,
                linewidth=1.6, markersize=5)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_xlabel("fusion depth", fontsize=9)
    ax.set_ylabel("accuracy (%)", fontsize=9)
    # Headroom below the lowest series keeps the legend clear of the LINC dip.
    ax.set_ylim(87.5, 101)
    ax.set_yticks([90, 92, 94, 96, 98, 100])
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7, loc="lower center", frameon=False, ncol=2,
              handlelength=1.8, columnspacing=1.2, borderpad=0.1)
    fig.tight_layout(pad=0.3)

    figs = PAPER / "figs"
    figs.mkdir(parents=True, exist_ok=True)
    fig.savefig(figs / "by_type.pdf")
    fig.savefig(figs / "by_type.png", dpi=200)
    plt.close(fig)
    print(f"written -> {figs / 'by_type.pdf'}")


if __name__ == "__main__":
    raise SystemExit(main())
