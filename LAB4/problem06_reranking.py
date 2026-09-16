# -*- coding: utf-8 -*-
"""Problem 06 - Re-ranking: what it can fix, what it cannot, and what it costs.

Where it came from
    LAB3 (DL-04), `src/rerankers.py` and `evaluation/eval_retrieval.py`.

The course template shows a first-stage retriever weighting generic terms
equally, a hand-written second pass that adds +3 for a specific term, and the
relevant document moving up. The mechanism is right. What it cannot show,
because the second pass is three lines of hard-coded term weights, is the two
things that decided whether reranking shipped:

  1. **A reranker can only reorder what retrieval already found.** It moves
     rank-sensitive metrics - MRR, nDCG, hit@1 - and leaves set-membership
     metrics alone. Measured in LAB3: MRR +6.3 %, hit@1 +13.0 %, and hit@10 does
     not move by a single point.
  2. **It costs 323x the latency.** BAAI/bge-reranker-v2-m3 is a 568M-parameter
     cross-encoder scoring CANDIDATE_K=20 query-document pairs per query on CPU.
     4035 ms against hybrid's 12.5 ms.

Those two numbers together are the whole decision, and the project has answered
it both ways: USE_RERANK shipped False on the strength of the latency, and is
True in the current config now that generation runs on a hosted model and several
seconds per answer is the baseline anyway. The point of measuring both states is
that the trade can be re-opened rather than argued about - so this module reads
the live value out of config.py instead of asserting one.
"""

import re

import data_loader as dl


def live_default(switch):
    """The value `switch` currently has in LAB3/RAG-Project/config.py."""
    match = re.search(rf"^{switch}\s*=\s*(True|False)",
                      dl.read_text(dl.CONFIG_PATH), re.MULTILINE)
    return match.group(1) == "True" if match else None


def run():
    dl.title("PROBLEM 06  Top-k and re-ranking")

    dl.section("A. the mechanism, on a toy scorer")
    entries = [entry for entry in dl.load_qa() if entry["lang"] == "ทางการ"]

    query = "เผลอบอกรหัส OTP ไปแล้ว ต้องอายัดบัญชีธนาคารไหม"
    generic = ["บัญชี", "ธนาคาร", "เงิน"]
    specific = ["อายัด", "1441"]

    def first_stage(entry):
        text = entry["question"] + entry["answer"]
        return sum(term in text for term in generic)

    def rerank(entry):
        text = entry["question"] + entry["answer"]
        return first_stage(entry) + sum(3 for term in specific if term in text)

    candidates = sorted(entries, key=first_stage, reverse=True)[:8]
    reordered = sorted(candidates, key=rerank, reverse=True)

    dl.kv("query", query)
    dl.kv("terms the first stage matches on", generic)
    dl.kv("terms the reranker rewards", specific)
    print()
    dl.table(["stage-1", "rerank", "question"],
             [[first_stage(entry), rerank(entry), dl.clip(entry["question"], 46)]
              for entry in candidates],
             align_right={0, 1})
    print()
    print("  after re-ranking:")
    dl.table(["stage-1", "rerank", "question"],
             [[first_stage(entry), rerank(entry), dl.clip(entry["question"], 46)]
              for entry in reordered],
             align_right={0, 1})
    target = max(candidates, key=rerank)
    print()
    dl.kv("the document that answers the query", dl.clip(target["question"], 40))
    dl.kv("its rank before / after",
          f"{candidates.index(target) + 1} -> {reordered.index(target) + 1}")
    print()
    dl.para("A first-stage retriever weights every matching term the same, so a document that "
            "mentions the generic words often outranks the one document that answers the "
            "specific question. A second pass with finer-grained signals pulls it back up. "
            "Note that every document in the second table also appears in the first: reranking "
            "reorders a candidate set, it cannot add to it.")

    dl.section("B. what that costs and buys, measured over 216 queries")
    try:
        results = dl.eval_retrieval()["results"]
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    metrics = ["hit@1", "hit@10", "mrr", "ndcg@3"]
    rows = []
    for name, data in results.items():
        overall = data["overall"]
        rows.append([name] + [f"{overall[metric]:.4f}" for metric in metrics] +
                    [f"{data.get('ms_per_query', float('nan')):.1f}"
                     if "ms_per_query" in data else "-"])
    dl.table(["run"] + metrics + ["ms/query"], rows,
             align_right=set(range(1, len(metrics) + 2)))

    hybrid = results["hybrid"]["overall"]
    reranked = results["hybrid+rerank"]["overall"]

    print()
    dl.table(["metric", "hybrid", "hybrid+rerank", "change"],
             [[metric, f"{hybrid[metric]:.4f}", f"{reranked[metric]:.4f}",
               f"{(reranked[metric] - hybrid[metric]) / hybrid[metric] * 100:+.1f} %"
               if hybrid[metric] else "n/a"]
              for metric in metrics],
             align_right={1, 2, 3})

    print()
    dl.para("hit@1 moves the most, MRR and nDCG@3 move, and hit@10 does not move at all. That "
            "is the signature of a reranker working correctly rather than a measurement error: "
            "a cross-encoder reorders the candidate set, so it can promote a chunk that was "
            "already retrieved and can never pull in one that was missed. Here hybrid had "
            "already driven hit@10 to 1.0000, so there was nowhere for it to go even in "
            "principle.")

    dl.section("C. the number the decision turns on")
    slow = results["hybrid+rerank"].get("ms_per_query")
    fast = results["hybrid"].get("ms_per_query")
    if slow and fast:
        dl.kv("hybrid", f"{fast:.1f} ms/query")
        dl.kv("hybrid + cross-encoder rerank", f"{slow:.1f} ms/query")
        dl.kv("ratio", f"{slow / fast:.0f}x slower")
    dl.kv("model", "BAAI/bge-reranker-v2-m3, 568M parameters, CPU")
    dl.kv("pairs scored per query", "CANDIDATE_K = 20")
    dl.kv("pairs scored in the whole run", "20 x 216 = 4320")
    print()
    dl.kv("USE_RERANK in config.py right now", live_default("USE_RERANK"))
    print()
    dl.para("Four seconds per query is not a tuning number, it is a product decision, and the "
            "project has landed on both sides of it. It shipped False while generation ran on "
            "a local llama3.1:8b and 12.5 ms was the whole cost of a search. It is True now "
            "that generation runs on a hosted model that takes seconds of its own - on that "
            "baseline the reranker is no longer what makes the system slow, and it is the most "
            "accurate configuration measured anywhere in the project.")
    print()
    dl.para("Neither answer is the finding. The finding is that the switch has a measurement "
            "attached to it in both states, so changing it is a decision someone can re-open "
            "with numbers rather than an assumption nobody wrote down. Lowering CANDIDATE_K, "
            "moving the cross-encoder to a GPU, or picking a smaller one would all move the "
            "4035 ms, and the comparison is set up to say by how much.")

    dl.section("Cause")
    dl.para("First-stage retrieval optimises for recall at low cost: get the right chunk into "
            "the candidate set. Ranking precisely within that set is a different and much more "
            "expensive computation, because a cross-encoder reads the query and the document "
            "together instead of comparing two vectors that were computed separately. Asking "
            "one stage to do both jobs is what leaves the right answer buried in the "
            "middle of the candidate list.")

    dl.section("Fix applied in LAB3")
    dl.bullet("Two-stage retrieval: hybrid pulls CANDIDATE_K = 20 candidates, the cross-encoder "
              "reorders them down to TOP_K = 3.")
    dl.bullet("USE_RERANK is a switch in config.py and eval_retrieval.py scores both states, so "
              "the gain and the cost are numbers rather than opinions.")
    dl.bullet("The default is documented next to the measurement that justifies it, and moved "
              "from False to True when the generation backend changed - which is the switch "
              "doing its job.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/rerankers.py, "
            "LAB3/RAG-Project/evaluation/eval_retrieval.py")


if __name__ == "__main__":
    run()
