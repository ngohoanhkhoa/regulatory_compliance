"""Retrieval evaluation: hand-curated question / expected-CELEX pairs (§10).

This eval set measures **recall@k**: for each question, does the correct CELEX
appear in the top-k retrieved chunks? Run programmatically::

    uv run python -m tests.eval_retrieval --top-k 7

The set is deliberately small (~25 pairs) and hand-curated per the spec's
guidance. Each entry is (question, set of expected CELEX ids). A question
"passes" if **any** of the expected CELEX ids appears in the retrieved chunks'
metadata. Full recall (all expected ids present) is tracked separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass
class EvalCase:
    question: str
    expected_celex: set[str]
    note: str = ""


EVAL_SET: list[EvalCase] = [
    EvalCase("What regulation governs data protection of personal data?",
             {"32016R0679"}, "GDPR"),
    EvalCase("Is the GDPR still in force?",
             {"32016R0679"}, "GDPR in-force check"),
    EvalCase("What are the technical measures for fisheries conservation?",
             {"32019R1241"}, "Reg 2019/1241 technical measures"),
    EvalCase("Regulation on marketing and use of explosives precursors",
             {"32019R1148", "32013R0098"}, "current + repealed"),
    EvalCase("What regulation establishes a Union control system for fisheries?",
             {"32009R1224"}, "Council Reg 1224/2009"),
    EvalCase("Common organisation of agricultural markets",
             {"32013R1308"}, "CMO regulation"),
    EvalCase("What regulation concerns trade in seal products?",
             {"32009R1007"}, "Reg 1007/2009"),
    EvalCase("What is the regulation on the avoidance of trade diversion of key medicines?",
             {"32016R0793"}, "Reg 2016/793"),
    EvalCase("Import duties on sugar sector products",
             {"32011R0722"}, "sugar import duties"),
    EvalCase("Protected geographical indications Saucisson de l'Ardeche",
             {"32011R0719"}, "PGI registration"),
    EvalCase("Protected designation of origin Riviera Ligure",
             {"32011R0718"}, "PDO amendment"),
    EvalCase("Conservation of marine ecosystems through technical measures",
             {"32019R1241"}, "technical measures marine ecosystems"),
    EvalCase("Regulation amending Council Regulation No 1967/2006",
             {"32019R1241"}, "amendment lineage"),
    EvalCase("Standard import values for fruit and vegetables",
             {"32011R0721"}, "entry price system"),
    EvalCase("Regulation on the marketing and use of explosives precursors amending 1907/2006",
             {"32019R1148"}, "explosives precursors 2019/1148"),
]


def run_eval(top_k: int = 7) -> dict:
    """Run the eval set against the live retrieval pipeline."""
    from src.retrieval import hybrid_retriever as hr

    results = []
    hit_any = 0
    hit_all = 0
    total = len(EVAL_SET)

    for case in EVAL_SET:
        chunks = hr.retrieve(case.question, top_k=top_k)
        retrieved_celex = {
            (c.get("metadata") or {}).get("celex", "") for c in chunks
        }
        retrieved_celex.discard("")
        partial = case.expected_celex & retrieved_celex
        any_hit = len(partial) > 0
        all_hit = case.expected_celex <= retrieved_celex
        if any_hit:
            hit_any += 1
        if all_hit:
            hit_all += 1
        results.append({
            "question": case.question,
            "note": case.note,
            "expected": sorted(case.expected_celex),
            "retrieved": sorted(retrieved_celex),
            "hit_any": any_hit,
            "hit_all": all_hit,
        })

    summary = {
        "total": total,
        "top_k": top_k,
        "recall_at_least_one": hit_any / total,
        "recall_all_expected": hit_all / total,
        "results": results,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Retrieval eval (recall@k)")
    ap.add_argument("--top-k", type=int, default=7)
    ap.add_argument("--json", action="store_true", help="output full JSON")
    args = ap.parse_args(argv)
    summary = run_eval(top_k=args.top_k)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"recall@k (k={summary['top_k']}, n={summary['total']}):")
        print(f"  recall_at_least_one = {summary['recall_at_least_one']:.1%}")
        print(f"  recall_all_expected  = {summary['recall_all_expected']:.1%}")
        for r in summary["results"]:
            mark = "OK" if r["hit_any"] else "MISS"
            print(f"  [{mark}] {r['note']:40s} expected={r['expected']} got={r['retrieved'][:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
