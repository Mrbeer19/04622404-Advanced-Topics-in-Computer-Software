# -*- coding: utf-8 -*-
"""Problem 09 - Evaluation: the bugs in the measurement, and the benchmark that lies.

Where it came from
    LAB3 (DL-04), `evaluation/eval_retrieval.py`, `evaluation/build_golden_set.py`.

The course template prints chunk ranges and then narrates a hypothetical - "the
relevant document is at rank 8, so Top-5 misses it and Top-10 finds it". Nothing
is computed and no golden set is used, so the part of evaluation that actually
goes wrong never appears.

Three things went wrong with the measurement in LAB3, and they are in increasing
order of how much they cost:

  1. **An accumulator that was an assignment.** `all_misses = misses` inside the
     configuration loop overwrote the list every round, so the "not retrieved"
     report only ever described the last configuration. The metric numbers were
     fine; the diagnostic that explains them was silently wrong.
  2. **Metrics named after things they do not measure.** "correctness" is word
     overlap with a reference answer. An answer that is right in different words
     scores low.
  3. **A golden set that leaks its answers.** Every query variant is built from
     the target question by string operations, so nearly every token of the
     target survives into the query. BM25 then scores 0.9933 MRR - which is not
     a finding about BM25, it is a finding about the benchmark.
"""

import collections

import data_loader as dl


# ------------------------------------------------------------- the accumulator bug

def eval_broken(configurations):
    """The shipped loop: `all_misses = misses` replaces instead of accumulating."""
    all_misses = []
    for name, misses in configurations:
        all_misses = misses          # <- the defect, verbatim
    return all_misses


def eval_fixed(configurations):
    """The LAB3 loop: accumulate, and tag each row with the run it came from."""
    all_misses = []
    for name, misses in configurations:
        all_misses += [(name,) + miss for miss in misses]
    return all_misses


def token_overlap(query, target):
    """The fraction of `target`'s characters that also appear in `query`.

    Whitespace tokens are useless for Thai (problem02), so this measures at the
    character level. It is crude, and it is enough to show the leak.
    """
    target_chars = set(target)
    if not target_chars:
        return 0.0
    return len(target_chars & set(query)) / len(target_chars)


def run():
    dl.title("PROBLEM 09  Evaluating the system, and the evaluation itself")

    # ------------------------------------------------------------------ 1
    dl.section("A. an accumulator that was an assignment")
    configurations = [
        ("dense_only", [("g0012", "query a"), ("g0031", "query b")]),
        ("bm25_only", [("g0044", "query c")]),
        ("hybrid", [("g0068", "query d")]),
    ]
    broken = eval_broken(configurations)
    fixed = eval_fixed(configurations)

    dl.kv("misses produced across the three runs",
          sum(len(misses) for _, misses in configurations))
    dl.kv("rows the shipped report showed", len(broken))
    dl.kv("rows the fixed report shows", len(fixed))
    print()
    print("  shipped:")
    for row in broken:
        dl.bullet(str(row))
    print("  fixed:")
    for row in fixed:
        dl.bullet(str(row))
    print()
    dl.para("The scores were never affected, which is what made this survive: the table of "
            "numbers looked right and only the 'these queries failed' section under it was "
            "wrong. It reported the last configuration's misses under every configuration's "
            "name, so the one output that explains why a run scored what it scored was "
            "systematically misleading. The fix accumulates and tags each row with its run.")

    # ------------------------------------------------------------------ 2
    dl.section("B. the golden set derives its queries from its answers")
    try:
        golden = dl.golden_set()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    items = golden["items"]
    variants = collections.Counter()
    for item in items:
        variants.update(item["variants"].keys())

    dl.table(["variant", "items", "how build_golden_set.py makes it"],
             [["verbatim", variants["verbatim"], "the question itself"],
              ["natural", variants["natural"], "'สงสัยว่า' + the question + ' ยังไงคะ'"],
              ["partial", variants["partial"], "the question with stopwords dropped"],
              ["slang", variants["slang"], "terms swapped through the TO_SLANG table"]],
             align_right={1})

    print()
    overlaps = collections.defaultdict(list)
    for item in items:
        for name, query in item["variants"].items():
            overlaps[name].append(token_overlap(query, item["question"]))

    dl.table(["variant", "mean character overlap with the target question"],
             [[name, f"{sum(values) / len(values):.3f}"]
              for name, values in sorted(overlaps.items(),
                                         key=lambda pair: -sum(pair[1]) / len(pair[1]))],
             align_right={1})

    print()
    dl.para("Every variant keeps almost all of the target's characters. `natural` - the variant "
            "the course notes treat as the deciding case - is the original question with a "
            "prefix and a suffix glued on, which changes nothing at all for a bag-of-words "
            "scorer.")

    dl.section("C. what that does to the scoreboard")
    try:
        results = dl.eval_retrieval()["results"]
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    dl.table(["run", "MRR", "hit@1"],
             [[name, f"{data['overall']['mrr']:.4f}", f"{data['overall']['hit@1']:.4f}"]
              for name, data in results.items()],
             align_right={1, 2})
    print()
    dl.para("BM25 wins the benchmark outright, beating hybrid and even beating hybrid with a "
            "568M-parameter cross-encoder on top. Read at face value that says keyword matching "
            "is the best retrieval method available and the whole dense pipeline was a waste. "
            "The real explanation is in the table above it: BM25 matches tokens, and nearly "
            "every token of the target is still sitting in the query.")
    print()
    dl.para("So the bm25_only column measures how well a method handles lightly edited copies "
            "of the target, not how it handles a user's phrasing. The dense and hybrid columns "
            "remain informative relative to each other, and `slang` is the one variant with "
            "real teeth - which is exactly where the dense-vs-hybrid gap opens up. Note from "
            "problem03 that even the slang variants are ~97 % character-identical to their "
            "source in five cases, so that variant is weaker than it looks too.")

    dl.section("D. metrics named after things they do not measure")
    try:
        summary = dl.eval_generation()["summary"]
    except dl.MissingArtefact as error:
        print(f"  {error}")
        summary = {}

    dl.table(["name", "value", "what the code computes", "trustworthy?"],
             [["faithfulness", summary.get("faithfulness", "-"),
               "answer words present in the context", "yes, for drift"],
              ["correctness", summary.get("correctness", "-"),
               "answer words present in the reference", "no"],
              ["relevance", summary.get("relevance", "-"),
               "question words present in the answer", "no"]])
    print()
    dl.para("word_overlap() counts how many tokens of one text appear in another. That is a "
            "reasonable proxy for 'the answer did not wander away from its source', which is "
            "what faithfulness needs. It is not a proxy for correctness: an answer that is "
            "right in different words scores low, and a wrong answer that reuses the "
            "reference's vocabulary scores high. Grading correctness needs an LLM judge or a "
            "human reader, and neither was in scope for LAB3 - so the number stays, with what "
            "it actually means written next to it.")

    dl.section("Cause")
    dl.para("Evaluation code is the code nobody evaluates. A bug in the pipeline shows up as a "
            "bad answer; a bug in the measurement shows up as a good number, which is the one "
            "outcome nobody investigates. The golden set is the sharper version of the same "
            "problem: it was generated from the corpus it tests, so it was guaranteed to be "
            "passable from the day it was written.")

    dl.section("Fix applied in LAB3")
    dl.bullet("The misses accumulator was corrected and each row now carries its run name.")
    dl.bullet("metrics.py has a self-test (`python -m evaluation.metrics`) that checks the "
              "formulas against hand-computed cases, so a metric bug fails loudly.")
    dl.bullet("The leak is documented in LAB3/README.md next to the table it explains, and "
              "bm25_only's 0.9933 is reported as a warning rather than a result.")
    dl.bullet("correctness and relevance are reported with their definitions attached.")
    print()
    dl.para("Still open: fixing the benchmark properly needs queries that share intent but not "
            "vocabulary with the target, which means hand-written questions or an LLM "
            "generating them plus a manual check - an LLM paraphrase can silently change what "
            "was asked. That is a larger piece of work than the lab had room for, and saying "
            "so is more useful than quietly keeping the 0.9933.")
    print()
    dl.para("Source: LAB3/RAG-Project/evaluation/eval_retrieval.py, "
            "evaluation/build_golden_set.py, evaluation/metrics.py")


if __name__ == "__main__":
    run()
