# How the benchmark was built, and how the evaluated configuration answers

Two things are documented here: the question-generation pipeline, in enough
detail to be reimplemented, and a sketch of the configuration under study, at
the level the comparison requires. The system's implementation is not part of
this repository.

## 1. Question generation

**No language model takes part in producing a question or a gold answer.** This
is the point of the design. The usual objection to a generated benchmark is that
the model under test also wrote the answers; here every gold value is either
copied from the source record or derived by a description-logic reasoner, so
that objection does not apply.

### 1.1 Source records

Industrial partners in the [CE-RISE](https://cordis.europa.eu/project/id/101092281)
project supplied bills of materials for batteries, printers and heating
appliances. These were normalised into Digital Product Passport records with a
fixed field vocabulary, unit convention and identifier scheme.

Each record is then emitted in **two forms describing the same product**:

| form | what it is | which depths it serves |
|---|---|---|
| passport document | semi-structured, labelled fields | recall, open |
| OWL/RDF individual | typed entity in a domain ontology | recall, rule |

Emitting both is what allows the same product to be questioned two ways and
scored identically.

### 1.2 Generators

| depth | source | question form | gold comes from |
|---|---|---|---|
| recall | asserted triples (2,594) **and** document fields whose gold is a measured quantity (145) | *According to `<doc>`, what is the `<field>`?* / *What is the `<p>` of `<s>`?* | the stated value |
| open | document fields whose gold is not a measured quantity (860) | *According to `<doc>`, what is the `<field>`?* | every part of the value |
| rule | entailed-but-not-asserted types | *Is `<s>` a `<C>`?* | `label(C)`, by entailment |

**How recall and open are actually separated.** Depth one is overwhelmingly
graph lookup: 2,594 of its 2,750 questions come from asserted triples and only
145 from documents. Depth two is entirely document-derived (860 of 871).

Within the 1,005 document-derived questions the two labels share a surface form,
and the generator separates them by a single mechanical test on the **gold
value**:

```python
NUMERIC_RE = re.compile(
    r"\b\d+(?:[\.,]\d+)?\s?(?:kWh|Wh|W|kW|V|mAh|Ah|A|°C|C|kg|g|mm|cm|m|%"
    r"|ppm|bar|psi|years?|months?|days?|pages?|s|dpi|MB|GHz)\b", re.I)

qtype = "recall" if NUMERIC_RE.search(expected) else "open"
```

A gold value carrying a measured quantity is depth one; anything else is depth
two. Re-applying this test to the released CSVs reproduces the published labels
for **100%** of those 1,005 rows, so the rule is checkable rather than asserted.

**This is a proxy, not a definition.** It captures the intended contrast — a
measurement is a single self-contained value, while a non-measurement field is
more often a name, a description or a list — but it is a lexical test, and the
depth-one/depth-two boundary should be read as approximate on the document side.

The measurable consequence is answer shape. Depth-two golds are longer (29.8 vs
19.5 characters) and more often compound (38% vs 19% contain an internal
separator), and compoundness is what carries the difficulty: within `open`,
LongCtx answers 99.63% of atomic-gold questions but 91.38% of the 325
compound-gold ones.

**Every question uses one of three templates.** There are no existential,
temporal, quantitative or negated forms and no paraphrase variation. This keeps
gold answers mechanically derivable, but it means the benchmark says nothing
about robustness to question phrasing. Widening the templates would require
regenerating the benchmark and re-running every configuration, so the released
generator emits exactly the forms present in the released data — no more.

### The rule branch

The rule branch is the only one that computes anything. The asserted graph is expanded
under [OWL 2 RL](https://www.w3.org/TR/owl2-profiles/) entailment, and a
question is generated **only** where a type assertion appears in the closure but
not in the source. The answer is therefore not written anywhere in the record
and cannot be found by searching it.

`scripts/generate_schema_questions.py` is a runnable reference implementation of
that step:

```bash
pip install rdflib owlrl
python scripts/generate_schema_questions.py
```

```
2 schema-governed questions generated

  Q: Is LiCell-014 a Battery?
     gold: Battery   (entailed_not_asserted)
  Q: Is LiCell-014 a Product?
     gold: Product   (entailed_not_asserted)
```

The worked ontology states only that `LiCell-014` is a `RechargeableBattery`.
That it is also a `Battery` and a `Product` follows from the subclass chain —
which is exactly what makes these depth-three questions.

Point the script at your own ontology with `--ttl`.

### 1.3 Mechanical filters

Applied at generation time:

- **per-subject cap** of six questions, so a densely described product cannot
  dominate the set;
- **exact de-duplication** on the pair `(question, gold)`.

### 1.4 Verification filter

A generated question can be well formed and still have no uniquely determined
answer. 645 were removed under eight criteria, each a property of the source
record and each decidable without running any configuration:

| criterion | removed |
|---|---:|
| entity carries two conflicting relations | 256 |
| document label malformed | 146 |
| gold not uniquely supported by the record | 94 |
| gold is a placeholder, not a value | 75 |
| gold is a list where one item is expected | 28 |
| record-level class not verifiable | 21 |
| class not derivable under entailment | 15 |
| document label ambiguous | 10 |
| **total removed** | **645** |
| **retained** | **6,270** |

Every excluded row is published in `data/verified/exclusions.csv` with its
reason, so a reader who disagrees with a criterion can recompute without it.

### 1.5 Scoring

A configuration is correct when its answer contains the gold value as a
substring, after whitespace normalisation. The rule is identical for all four
configurations. It is deliberately simple, and it has two consequences that
`scripts/analysis_clean.py` quantifies rather than hides: an explicit refusal is
scored as a wrong answer, and a refusal that happens to contain the gold
substring is scored as correct.

## 2. The configuration under study

Described only as far as the comparison requires. Three modules are engaged
according to what a question needs, rather than uniformly:

```
question
   │
   ├─► base memory        values already established for this product
   │                       in this session
   │
   ├─► external memory    retrieval over passport documents and the
   │                       ontology, for whatever base memory did not resolve
   │
   ├─► reasoner           invoked only when the question needs a fact the
   │                       record does not state; derives it from the schema,
   │                       or reports that it cannot
   │
   ├─► gate               if the assembled evidence does not cover every
   │                       component the question asks for → ABSTAIN
   │
   └─► context → LLM      compose an answer from the assembled context alone
```

Two properties matter for the reported results. The modules are engaged on
demand rather than run as a fixed pipeline, which is what *depth-aware* refers
to. And the gate is placed before generation, not after: a question with thin
evidence lowers coverage instead of producing a confident guess. That is the
mechanism behind the coverage and calibration figures in
`data/public_schema/`.

**Not documented here:** the internal design of each module, how they are
coordinated, and the contribution each makes. Those are reported separately.
