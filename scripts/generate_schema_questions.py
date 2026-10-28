#!/usr/bin/env python3
"""Reference implementation of the schema-governed question generator (Alg. 1).

This is the step of the benchmark pipeline that is worth being able to inspect,
because it is the one that decides what a depth-three question is. A question is
generated only where a type assertion is *entailed* by the ontology but is
*not asserted* in it. The gold answer is therefore produced by a reasoner, never
by a language model, and it is not written anywhere in the source record.

Run it on the worked example shipped here:

    pip install rdflib owlrl
    python scripts/generate_schema_questions.py

or on your own ontology:

    python scripts/generate_schema_questions.py --ttl mine.ttl

What is NOT in this file: the document and recall generators are simple field
and triple walks and are described in docs/BENCHMARK_GENERATION.md; the system
being evaluated is not part of this repository at all.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rdflib import Graph, RDF, RDFS, OWL, URIRef
from owlrl import DeductiveClosure, OWLRL_Semantics

# A miniature product ontology in the shape of the real ones: a few asserted
# facts, and a class hierarchy that entails more than it states. Nothing here is
# partner data.
EXAMPLE_TTL = """
@prefix ex:   <https://example.org/dpp#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .

ex:Product            a owl:Class .
ex:Battery            a owl:Class ; rdfs:subClassOf ex:Product .
ex:RechargeableBattery a owl:Class ; rdfs:subClassOf ex:Battery .
ex:Component          a owl:Class .

ex:hasCapacity        a owl:DatatypeProperty .
ex:suppliedBy         a owl:ObjectProperty .

# Asserted: LiCell-014 is a rechargeable battery, and two plain facts about it.
ex:LiCell-014  a ex:RechargeableBattery ;
               rdfs:label "LiCell-014" ;
               ex:hasCapacity "3000 mAh" ;
               ex:suppliedBy ex:PrintPack .

ex:PrintPack   a ex:Component ; rdfs:label "PrintPack" .
"""


def label(g: Graph, u: URIRef) -> str:
    lab = next((str(o) for o in g.objects(u, RDFS.label)), None)
    if lab:
        return lab
    s = str(u)
    return s.split("#", 1)[1] if "#" in s else s.rsplit("/", 1)[1]


def generate(ttl_text: str | None, ttl_path: Path | None) -> list[dict]:
    asserted = Graph()
    if ttl_path:
        asserted.parse(ttl_path.as_posix(), format="turtle")
    else:
        asserted.parse(data=ttl_text, format="turtle")

    # Entailment closure. `closed` contains everything `asserted` contains plus
    # everything OWL-RL can derive from it.
    closed = Graph()
    for t in asserted:
        closed.add(t)
    DeductiveClosure(OWLRL_Semantics).expand(closed)

    asserted_types = {(s, o) for s, _, o in asserted.triples((None, RDF.type, None))}

    out = []
    for s, _, c in closed.triples((None, RDF.type, None)):
        if (s, c) in asserted_types:
            continue                       # stated outright: not depth three
        if not isinstance(c, URIRef) or not isinstance(s, URIRef):
            continue
        # Skip the vocabulary of the modelling language itself. Questions about
        # owl:Thing, rdfs:Class and the XSD datatypes are about the schema
        # language rather than the product; the paper reports separately what
        # happens if they are kept (see the limitations section of the README).
        if str(c).startswith(("http://www.w3.org/2002/07/owl#",
                              "http://www.w3.org/2000/01/rdf-schema#",
                              "http://www.w3.org/2001/XMLSchema#")):
            continue
        out.append({
            "type": "logic",
            "query": f"Is {label(closed, s)} a {label(closed, c)}?",
            "expected_contains": label(closed, c),
            "provenance": "entailed_not_asserted",
        })

    # Same two mechanical filters as the full pipeline.
    seen, dedup = set(), []
    for q in out:
        k = (q["query"], q["expected_contains"])
        if k not in seen:
            seen.add(k)
            dedup.append(q)
    return sorted(dedup, key=lambda q: q["query"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttl", type=Path, default=None,
                    help="ontology to read; omit to use the worked example")
    ap.add_argument("--out", type=Path, default=None,
                    help="write JSONL here instead of printing")
    a = ap.parse_args()

    qs = generate(None if a.ttl else EXAMPLE_TTL, a.ttl)

    if a.out:
        a.out.write_text("\n".join(json.dumps(q) for q in qs) + "\n")
        print(f"{len(qs)} questions -> {a.out}")
        return 0

    print(f"{len(qs)} schema-governed questions generated\n")
    for q in qs:
        print(f"  Q: {q['query']}")
        print(f"     gold: {q['expected_contains']}   ({q['provenance']})")
    if not a.ttl:
        print("\nNote what happened: the ontology never states that LiCell-014")
        print("is a Battery or a Product. Both follow from the subclass chain,")
        print("so both become questions whose answer cannot be found by")
        print("searching the record. That is what depth three tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
