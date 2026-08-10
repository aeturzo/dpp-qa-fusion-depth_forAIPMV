# COMPASS short paper — backup submission

A 4-page IEEE conference paper drawn from the COMPASS journal work, written so
that it can be submitted **without giving away the tool**. Held as a fallback in
case the score-semantics paper is not used.

## The angle: Intelligent Data Fusion

AIPMV's Algorithm track lists Natural Language Processing, **Intelligent Data
Fusion**, and Numerical Analysis. The paper is framed for the fusion track, and
the framing is not decorative — it is what the results are actually about.

Questions are grouped by **fusion depth**: how many kinds of source an answer
has to combine.

| depth | name | what it needs | $n$ |
|---|---|---|---|
| 1 | recall | one stated value in the record | 2,750 |
| 2 | open | several parts of the record | 871 |
| 3 | rule-governed | a record value **and** an external constraint | 2,649 |

The grouping is a property of the question, fixed before evaluation, and it
counts kinds of source rather than reasoning steps so it can be assigned without
judging difficulty.

## The finding

**A trade-off, not a ranking.** The three published systems sit within 2.11
points of each other overall, which reads as three comparable systems. Split by
fusion depth they are not comparable at all:

| configuration | recall | open | rule | overall |
|---|---|---|---|---|
| LongCtx | **99.93** | 96.56 | 93.09 | 96.57 |
| LINC | 95.45 | 91.62 | **95.36** | 94.88 |
| LogicLM | **99.96** | **97.82** | 93.62 | 96.99 |
| headroom to ceiling | 0.04 | 2.18 | 4.64 | |
| fused + selective | 100.00 | 100.00 | 100.00 | 100.00 |

Three things fall out, all recomputed from the artifacts on every build:

1. **Locating a stated value is solved.** LongCtx and LogicLM are at 99.93 and
   99.96. Further work on retrieval has ~0.04 points left to recover.
2. **LINC inverts.** It is the *best* of the three on rule-governed questions
   (95.36) and the *worst* on both other depths (95.45, 91.62). It translates
   every question into a formal representation, so it applies deep-fusion
   machinery to questions that need none and pays for it. Depth-three capability
   bought uniformly is not free.
3. **Headroom rises monotonically with depth:** 0.04 → 2.18 → 4.64.

This is what makes the paper a fusion paper rather than a system paper: the
argument is that fusion should be matched to the depth a question needs, and the
evidence is that both uniform strategies are punished at one end or the other.

**Why the paired result matters here.** Average accuracy cannot settle whether a
selective strategy avoids the trade-off, because LINC also improves on average
while losing cases elsewhere. On identical rows: 215 / 321 / 189 questions
answered correctly only by the selective configuration, and **0** answered
correctly only by a baseline (exact McNemar, $p < 10^{-56}$). Where LINC bought
rule accuracy by giving up recall accuracy, selective validation gave up nothing
measurable.

**Domain check.** Ordering the three domains by rule-governed share — battery
53.9%, lexmark 45.7%, viessmann 33.3% — baseline accuracy falls in the same
order (93.70 → 96.82 → 97.75). With 3 domains the paper reports this as an
ordering, not a correlation, and `make_numbers.py` re-derives the order on each
build rather than trusting the sentence.

**Generalisation arm.** 4,021 queries over Open Food Facts, a public schema the
system was not developed on: 97.21% decision accuracy [96.66, 97.68] at 73.0%
coverage, ECE 0.021, AURC 0.025, abstention precision 0.998 at recall 1.000.
Sustainability is the hardest slice at 91.92%, where coverage drops to 38.0% —
sparse fields mean little to combine, and the system declines rather than
guessing.

## Worked examples (Table II)

`make_examples.py` emits `paper/tab_examples.tex`: one real question per depth,
with all four systems' recorded answers, read from the locked CSVs. Rows are
pinned by `(id, query)` — **`id` alone is not unique, there are 449 duplicates** —
and the script aborts if a pinned row is missing or if a recorded verdict stops
matching what the table is built to show, so it can never emit a stale table.

| class | question | gold | the failure |
|---|---|---|---|
| basic | *…what is the Standard?* | 2 years parts & labour | LINC answers **EU F-Gas Regulation** — a real regulation, not the declared field |
| open | *…who is the EU authorised representative?* | Same as manufacturer | LINC answers the manufacturer's legal name — it resolved the reference instead of reporting the field |
| reasoning | *Is Gas a Thing?* | Thing | LongCtx and LogicLM decline from plausibility; the schema asserts it |
| multi-source | *preferred supplier + one compliance standard + Markings in the passport* | PrintPack · RoHS · separate collection symbol… | both baselines recover 2 of 3 and agree on **UN 38.3** — again a real standard, wrong here |

**Row 4 caveats, all stated in the caption and prose.** It comes from
`artifacts/paper_handoff_20260603/final_arch_3000_all3.csv` (the compositional
run), not the verified subset; **LINC was never run on it**; and it contributes
no number to any table — it is an illustration only. It is safe to include
because the baselines score 98.9–100% on the `memory_symbolic_*` subtypes,
which proves they *do* receive the session context, so this is a genuine fusion
failure and not an access gap. The paper describes the question's sources
neutrally as "a value the user set earlier in the session, a compliance
constraint, and a field from a passport document" — no memory subsystem,
persistence, or routing is named, and the system's `[record]` citation is
stripped as it is in every row.

Because that answer has three components and the systems differ on exactly one,
the cell lists the three components rather than the full sentence. Each
displayed fragment is **asserted to be a literal substring of the recorded
answer** before it is printed; the script aborts otherwise.

The common shape: every wrong answer is fluent, plausible, and substitutes the
system's own prior for what the record states. That is why answer-level review
does not catch them, and it is the qualitative case for the paired design.

## Known weaknesses in the benchmark (read before submitting)

`analysis_clean.py` re-reports the locked results read-only and writes
`CLEAN_REPORT.md`. Three properties of the released grading move the headline
numbers, and a reviewer with the artifacts can find all three:

1. **Scope.** None of the 88 `logic` templates contains a threshold, limit, or
   compliance comparison — they are all class-membership queries. 173 of 2,649
   ask about the ontology's own vocabulary (`Is decimal a Datatype?`) or whether
   a bare measurement is a class instance (`Is 18 V a Thing?`). Remove them and
   rule-depth accuracy goes LongCtx 93.09 → **98.99**, LogicLM 93.62 → **99.39**,
   LINC 95.36 → **99.88**. Headroom becomes 0.04 / 2.18 / **0.12** — no longer
   monotone, and rule becomes nearly the *easiest* depth.
2. **Abstention.** 250 of LINC's 321 errors (78%) are refusals, not wrong
   answers — 168 literal `INSUFFICIENT` plus 82 underived premise lists. Only
   ~71 are substantively wrong. 106 of the refusals are on *recall*, which is
   the "LINC is worst at lookup" half of the trade-off.
3. **Access asymmetry.** On the ontology-vocabulary subset the fused system
   scores 100% against a best baseline of 22.70%. LINC's answer there is always
   the same premise dump, meaning the OWL metamodel was never in its context.
   That is an information difference, not a reasoning difference.

**What survives all three:** the one-sided discordance. Baseline-only-correct is
**0** in every view — as published, and with the 173 rows removed (57 / 201 / 35
system-only-correct). That is the most defensible claim in the paper.

Cleaning was evaluated and **not adopted**: it removes the fusion-depth finding
without replacing it. The honest minimum before submission is to stop describing
depth three as a *regulatory* constraint — the benchmark contains no such
question — and to state the scope limit in §V.

## What it publishes, and what it holds back

**Published.** The fusion-depth analysis and the evaluation methodology: the
verified-subset construction with all 645 exclusions and their 8 reasons;
accuracy of four configurations on identical rows by depth and by domain; the
paired discordance result; the public-schema arm.

**Held back for the journal.** Everything about how the system works — the
architecture and its components, persistent memory, the symbolic layer's design,
routing, the RL work, ablations and component attribution, the carbon-footprint
subsystem, and the 3,000-row compositional benchmark.

The system is named only as "a configuration that applies symbolic validation
selectively", and the paper says explicitly that its internals and component
contributions are reported separately. A leakage check confirms the draft
contains no mention of COMPASS, CE-RISE, the RL work, the carbon layer, or
ablations.

This is a legitimate structure — a comparison paper with the system description
deferred — but a reviewer may still ask what the system is. The fusion framing
reduces the exposure: the contribution is the depth analysis and the trade-off
it reveals among *published* systems, which stands whether or not the fourth
configuration is described.

## Honest framing of the 100%

A perfect score invites suspicion and §V says so directly. The verified subset is
by construction the set of questions with unambiguous answers, and its
rule-governed portion is checked by deterministic validators, so a configuration
that routes those questions to the validator is *expected* to reach the ceiling.
The 645 exclusions are published so the boundary is inspectable rather than
asserted.

The interesting number is not the 100%. It is that LINC and LogicLM swap places
depending on which depth you score them at.

## Reproducibility

Every figure, table, and plot is derived. `make_numbers.py` reads only locked,
read-only artifacts and emits `numbers.tex`, `tab_domain.tex`, `tab_off.tex`,
and `figs/by_type.pdf`. Nothing is typed by hand, and claims about *ordering*
(domain ranking, headroom monotonicity) are recomputed rather than remembered —
the script prints whether each still holds.

| source | what it supplies |
|---|---|
| `artifacts/locked_results/verified_v1_20260521_173612_CEST/` | 6,270-row verified benchmark, four eval CSVs, exclusions |
| `artifacts/paper_handoff_20260603/off_system_eval_summary.csv` | 4,021-query public-schema arm |

```bash
python make_numbers.py          # regenerate all derived artifacts
cd paper && pdflatex main.tex && pdflatex main.tex
```

`main.bbl` is committed so the paper compiles where `IEEEtran.bst` is
unavailable; Overleaf has the style and will regenerate it from `refs.bib`.

Upload to Overleaf: `main.tex`, `numbers.tex`, `refs.bib`, `tab_domain.tex`,
`tab_off.tex`, `tab_examples.tex`, `figs/by_type.pdf`. Overleaf supplies
`IEEEtran.cls`. The preamble needs `array` (already added) for Table II.

## Status

Compiles clean: **5 pages, 0 errors, 0 undefined citations, 0 overfull boxes.**
Every macro used is defined; no macro is used that the generator does not emit.

AIPMV 2026 is **not** double-blind, so the paper ships with named authors and a
live repository URL.

Outstanding before submission:

1. **Author block and funding statement** — placeholders in `main.tex`.
2. **Repository URL** — replace `ORG` in the Reproducibility section once the
   GitHub repo exists (see `../GITHUB_UPLOAD_GUIDE.md`).
3. **The word "regulatory."** The abstract, introduction, §III and conclusion
   describe depth three as a regulatory constraint. The benchmark contains no
   such question — all 88 `logic` templates are class-membership queries. The
   released repository says so on its front page, so the paper and the artifact
   currently contradict each other. Fix the wording before publishing the link.

Nothing outside this directory was created or modified; the locked artifacts are
read only.
