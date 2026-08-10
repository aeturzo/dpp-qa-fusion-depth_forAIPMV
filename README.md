# Fusion depth in Digital Product Passport question answering

Data and verification code for the AIPMV 2026 paper *"Finding Evidence Is
Solved, Combining It Is Not: A Fusion-Depth Analysis of Question Answering over
Digital Product Passports."*

Everything the paper reports can be recomputed from this repository with one
command. Nothing in the paper is typed by hand: the values are generated into a
LaTeX macro file, and `scripts/verify_all.py` re-derives all of them from the
released CSVs and fails if any disagrees.

```bash
pip install -r requirements.txt
python scripts/verify_all.py
```

```
77 checks, 77 passed, 0 failed
Every number in the paper matches the released data.
```

## What the paper claims

Questions are grouped by **fusion depth** — how many kinds of source an answer
must combine. Depth one is a value stated in the record; depth two must be
assembled from several parts of it; depth three needs a record value *and* the
schema that classifies it — for example, whether a named component is an
instance of a declared product class.

| configuration | recall | open | schema | overall |
|---|---:|---:|---:|---:|
| LongCtx | **99.93** | 96.56 | 93.09 | 96.57 |
| LINC | 95.45 | 91.62 | **95.36** | 94.88 |
| LogicLM | **99.96** | **97.82** | 93.62 | 96.99 |
| depth-aware | 100.00 | 100.00 | 100.00 | 100.00 |

The three published systems sit within 2.11 points of each other overall, which
reads as three comparable systems. Split by depth they are not comparable: LINC
leads on schema-governed questions and trails on both others, and the two
systems that combine evidence loosely do the reverse. **No configuration is strong at
both ends.**

The most robust result is the paired one. On identical rows, the depth-aware
configuration answers correctly 215 / 321 / 189 questions that LongCtx / LINC /
LogicLM miss, and there is **no question that any baseline answers correctly and
it does not** — a zero that survives every re-grading in `analysis_clean.py`.

## Known limitations of this benchmark

We would rather state these than have a reader find them.

```bash
python scripts/analysis_clean.py
```

**1. The `logic` type is not about regulatory compliance.** None of its 88
question templates contains a threshold, limit, or compliance comparison; all
are class-membership queries under the schema. The paper calls this class
*schema-governed* for that reason. 173 of 2,649 go further and ask about the
schema vocabulary itself (`Is decimal a Datatype?`) or whether a bare
measurement is a class instance (`Is 18 V a Thing?`). Remove those 173 and
depth-three accuracy rises to 98.99 / 99.88 / 99.39, headroom becomes
0.04 / 2.18 / **0.12**, and the monotone relationship between depth and
difficulty **does not hold**.

**2. Refusals are scored as wrong answers.** 250 of LINC's 321 errors (78%) are
refusals, not incorrect answers. Only ~71 are substantively wrong. 106 of those
refusals fall on recall questions, which is the "LINC is weakest at lookup" half
of the trade-off.

**3. On the schema-vocabulary subset the baselines may not have had the
inputs.** LINC's answer there is always the same premise list, which is
consistent with the schema vocabulary never reaching its context. Read that
subset as an information difference, not a reasoning one.

What survives all three: the zero in the baseline-only column.

## Layout

```
data/verified/          6,270 questions × 4 configurations, plus 645 exclusions
data/public_schema/     4,021-query arm over Open Food Facts (summary level)
data/examples/          the single compositional question quoted in Table II
scripts/verify_all.py   recompute every reported number and check it
scripts/analysis_clean.py   re-report under stricter grading
paper/                  the generated macro file, tables and figure
CHECKSUMS.md            SHA-256 of every data file, and the withheld columns
```

## Joining these files correctly

`id` is **not unique** — 449 ids appear twice, on different products — and the
four files are not in the same row order. Join on `(id, query)`:

```python
a.merge(b, on=["id", "query"], validate="one_to_one")
```

Joining on `id` alone silently produces a cartesian product. `verify_all.py`
asserts the composite key is unique and that the join is lossless.

## What is not here

The system under study is described only as a configuration that applies
symbolic validation selectively and withholds an answer when the combined
evidence is insufficient. Its architecture and component analysis are reported
separately, so this repository contains **no system source code**, and the
per-question files are shipped without the instrumentation columns that describe
its internals. Every dropped column and the reason for dropping it is listed in
[`CHECKSUMS.md`](CHECKSUMS.md); no reported number depends on any of them.

The full compositional benchmark is also held back. `data/examples/` contains
only the one question shown in Table II, which contributes no number to any
table.

## Funding

This work was supported by the CE-RISE project, funded by the European Union's
Horizon Europe research and innovation programme under grant agreement
No. 101092281. Views and opinions expressed are those of the authors only and do
not necessarily reflect those of the European Union or the granting authority,
neither of which can be held responsible for them.

## Citation

See [`CITATION.cff`](CITATION.cff). Code is MIT; data is CC BY 4.0.
Open Food Facts data is used under the Open Database License.
