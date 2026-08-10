# Data card

## `verified/` — the verified evaluation subset

Four files, one per configuration, scored on **identical rows**: 6,270 questions
across three industrial domains (battery, printer, heating).

| file | configuration |
|---|---|
| `eval_longctx.csv` | a long-context language model reading the whole record |
| `eval_linc.csv` | LINC (Olausson et al., EMNLP 2023) |
| `eval_logiclm.csv` | Logic-LM (Pan et al., Findings of EMNLP 2023) |
| `eval_depth_aware.csv` | the configuration under study |

### Columns

| column | meaning |
|---|---|
| `id` | question identifier — **not unique**, see below |
| `type` | `recall`, `open`, or `logic` — the fusion depth |
| `domain` | `battery`, `lexmark`, or `viessmann` |
| `product` | the product record the question is about |
| `query` | the question as posed |
| `expected_contains` | the gold value; grading is substring containment |
| `answer` | the configuration's answer, verbatim |
| `correct` | 1 if `expected_contains` occurs in `answer`, else 0 |

### `id` is not a key

449 ids occur twice, on different products, and the four files are not in the
same row order. **Join on `(id, query)`**, which is unique and shared across all
four files. Joining on `id` alone silently produces a cartesian product.
`scripts/verify_all.py` asserts both properties.

### `exclusions.csv`

645 rows removed from the benchmark before evaluation, under 8 reasons, applied
without reference to any configuration's output. Columns: `id`, `domain`,
`type`, `reason`, `expected_contains`, `query`.

The exclusions and the scored set are disjoint on `(id, query)`. They overlap on
`id` alone in 154 cases — again, different questions sharing an id.

### Composition

| type | n | what an answer requires |
|---|---:|---|
| `recall` | 2,750 | one stated value |
| `open` | 871 | assembly from several parts of the record |
| `logic` | 2,649 | class membership under the schema |

See the limitations section of the top-level README before drawing conclusions
from the `logic` figures: 173 of those 2,649 concern the ontology's own
vocabulary rather than product content.

## `public_schema/` — generalisation arm

4,021 queries over [Open Food Facts](https://world.openfoodfacts.org/data), a
public product database with different field names and a great deal of genuinely
missing data. Summary level only; there is no per-question file.

| file | contents |
|---|---|
| `system_eval_summary.csv` | accuracy, Wilson interval, coverage, ECE, AURC, abstention precision/recall, per query type and overall |
| `calibration_bins.csv` | 10-bin reliability data |
| `ranked_risk_coverage.csv` | 5,868 points of the risk–coverage curve |

Accuracy here is **decision** accuracy: answering correctly when the record
supports an answer, and staying silent when it does not.

## `examples/` — one compositional question

`table2_multisource.csv` holds the three rows behind the last row of Table II:
one question requiring three sources, answered by three configurations. LINC was
not run on that evaluation, so it is absent rather than scored.

This is the **only** row released from the compositional benchmark, and it
contributes no number to any table in the paper. The `subtype` column was
dropped because it names an internal component.

## Provenance and grading

Results come from a single locked evaluation run; per-file SHA-256 checksums are
in [`../CHECKSUMS.md`](../CHECKSUMS.md).

Grading is substring containment of `expected_contains` in `answer`. Two
consequences are worth knowing, and both are quantified by
`scripts/analysis_clean.py`:

- an explicit refusal is scored as a wrong answer;
- a refusal that happens to contain the gold substring is scored as correct
  (this occurs 44 times, all for LINC).

## Known not to contain

No system source code, no model weights, no API keys, no credentials, and none
of the instrumentation columns describing the system under study. The dropped
columns and the reason for each are listed in `../CHECKSUMS.md`.
