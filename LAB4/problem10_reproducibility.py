# -*- coding: utf-8 -*-
"""Problem 10 - Reproducibility: measuring an LLM is not measuring a function.

Where it came from
    LAB3 (DL-04), `evaluation/eval_query_transform.py` and the two runs of the
    query-transform ablation.

The course template's main.py imports `problem10_debug_scripts`, which is not in
the repository - so `python main.py` raises ImportError before it prints the menu.
This module is what took that slot, and it is about the class of problem that
only shows up once a real model is in the loop.

Four findings, all from LAB3:

  1. **The model refuses, and the refusal becomes a search query.** llama3.1:8b
     is safety-tuned, the knowledge base is about how scams work, and a HyDE
     prompt asks it to invent a plausible answer describing a scam technique.
     18 of 68 HyDE prompts came back as an apology. query_transform.py cannot
     tell an apology from a hypothetical answer, so the apology went to the
     retriever as the query.
  2. **Identical code, identical settings, different numbers.** The ablation was
     run twice at LLM_TEMPERATURE = 0.2. `none` repeated exactly; every LLM mode
     moved, by up to 7.7 MRR points - more than four times the gap the ablation
     was trying to measure.
  3. **Timing noise produced a published conclusion that was wrong.** An earlier
     edition of the LAB3 results reported hybrid as faster than dense-only and
     concluded hybrid was better *and* cheaper. Hybrid runs dense retrieval and
     *then* BM25; it cannot be faster. Re-running put both at 12.5 ms.
  4. **A dependency that was optional in name only.** Without pythainlp,
     tokenize_thai() falls back to 3-character sliding windows and BM25 collapses
     - and the lesson shipped without a requirements.txt at all.
"""

import os

import data_loader as dl

# Two runs of evaluation/eval_query_transform.py, identical code and settings.
# Run 2 is the one committed to outputs/; run 1 is recorded here from the LAB3
# results table because a single run cannot show variance.
TWO_RUNS = {
    "none": (0.9228, 0.9228),
    "rewrite": (0.6130, 0.5364),
    "multi_query": (0.8811, 0.8713),
    "hyde": (0.8186, 0.8881),
}


def run():
    dl.title("PROBLEM 10  Reproducibility and debugging an LLM in the loop")

    dl.section("A. the refusal that became a search query")
    try:
        transform = dl.eval_query_transform()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    rows = []
    for mode, records in transform["transforms"].items():
        refusals = [record for record in records if record["refused"]]
        searched = sum(len(record["searched"]) for record in records) / len(records)
        rows.append([mode, len(records), len(refusals),
                     f"{len(refusals) / len(records):.0%}", f"{searched:.2f}"])
    dl.table(["mode", "prompts", "refusals", "rate", "queries searched"], rows,
             align_right={1, 2, 3, 4})

    worst = max(transform["transforms"],
                key=lambda mode: sum(r["refused"] for r in transform["transforms"][mode]))
    example = next(record for record in transform["transforms"][worst] if record["refused"])
    print()
    dl.kv("worst mode", worst)
    dl.kv("  the user asked", dl.clip(example["query"], 46), 20)
    for query in example["searched"]:
        dl.kv("  what was searched", dl.clip(query, 46), 20)
    print()
    dl.para("HyDE asks the model to write a plausible answer to the question and then searches "
            "for that answer instead of the question. On a knowledge base about how scams work, "
            "'invent a plausible answer describing this scam technique' reads to a safety-tuned "
            "model like a request for help committing one, and it declines. The declining "
            "sentence is a string, query_transform.py returns strings, and the retriever "
            "searches whatever it is handed.")
    print()
    dl.para("This is invisible unless the transformed queries are logged. The MRR would simply "
            "have been lower with no explanation. eval_query_transform.py records both the "
            "query it sent and a refusal flag, which is the only reason this is a diagnosis "
            "rather than a mystery.")

    dl.section("B. the same experiment, run twice")
    dl.table(["mode", "run 1 MRR", "run 2 MRR", "difference"],
             [[mode, f"{first:.4f}", f"{second:.4f}", f"{second - first:+.4f}"]
              for mode, (first, second) in TWO_RUNS.items()],
             align_right={1, 2, 3})
    print()
    moved = max(TWO_RUNS.items(), key=lambda item: abs(item[1][1] - item[1][0]))
    spread = abs(moved[1][1] - moved[1][0]) * 100
    gap = abs(TWO_RUNS["hyde"][1] - TWO_RUNS["multi_query"][1]) * 100
    dl.kv("largest movement between runs", f"{moved[0]}, {spread:.1f} MRR points")
    dl.kv("gap being measured (hyde vs multi_query)", f"{gap:.1f} MRR points")
    dl.kv("ratio", f"{spread / gap:.1f}x the effect size")
    dl.kv("deterministic mode", "none - repeated exactly, because no LLM is involved")
    print()
    dl.para(f"At LLM_TEMPERATURE = 0.2, with the same code and the same 68 queries, the numbers "
            f"moved by up to {spread:.1f} points between runs while the difference the ablation "
            f"was trying to measure is {gap:.1f} points. One run of 68 queries cannot separate "
            "hyde from multi_query at all. So the only claim the ablation supports is the part "
            "that held across both runs: every LLM mode scored below leaving the switch off. "
            "The magnitudes are noise and are reported as noise.")

    dl.section("C. a timing measurement that produced a wrong conclusion")
    try:
        results = dl.eval_retrieval()["results"]
        dl.table(["run", "ms/query"],
                 [[name, f"{data['ms_per_query']:.1f}"] for name, data in results.items()],
                 align_right={1})
    except dl.MissingArtefact as error:
        print(f"  {error}")

    print()
    dl.kv("earlier edition reported", "hybrid 7.9 ms, dense_only 11.9 ms")
    dl.kv("and concluded", "hybrid is both more accurate and faster")
    dl.kv("why that cannot be true",
          "hybrid does everything dense_only does, then runs BM25 as well")
    dl.kv("after re-running", "both 12.5 ms; BM25 costs 4.9 ms standalone")
    print()
    dl.para("The number was real, the conclusion drawn from it was not. A result that "
            "contradicts the structure of the code is a measurement error until proven "
            "otherwise - the ordering here was fixed by construction, so no timing run could "
            "reverse it. The correction is written into LAB3/README.md next to the table rather "
            "than quietly replacing it, because the mistake is the more useful half.")

    dl.section("D. the dependency that was optional in name only")
    requirements = os.path.join(dl.LAB3_PROJECT, "requirements.txt")
    dl.kv("requirements.txt in DL-03", "present")
    dl.kv("requirements.txt in DL-04 as shipped", "missing")
    dl.kv("added in LAB3", os.path.exists(requirements))
    if os.path.exists(requirements):
        packages = [line.strip() for line in dl.read_text(requirements).splitlines()
                    if line.strip() and not line.startswith("#")]
        dl.kv("pinned packages", len(packages))
        for package in packages:
            if "pythainlp" in package.lower():
                dl.kv("the one that is not optional", package)
    print()
    dl.para("Without pythainlp, tokenize_thai() falls back to sliding 3-character windows. BM25 "
            "still runs, still returns results and still produces a score - a much lower one - "
            "so the failure looks like 'BM25 is weak on Thai' rather than 'the tokeniser is not "
            "installed'. Every comparison in problem02 and problem06 would have been measuring "
            "that instead. A missing requirements.txt turns a hard dependency into a silent "
            "environment difference between two machines.")

    dl.section("Cause")
    dl.para("A retrieval pipeline is a function: same input, same output, and a difference in "
            "the numbers means a difference in the code. Adding an LLM breaks that property. "
            "The same prompt can come back as an answer, a shorter answer, or a refusal, and "
            "every measurement downstream inherits that spread. None of the usual instincts - "
            "run it once, compare the numbers, keep the better one - survive it.")

    dl.section("Fix applied in LAB3")
    dl.bullet("eval_query_transform.py logs every query actually sent to the retriever plus a "
              "refusal flag, so a score drop can be traced to specific prompts.")
    dl.bullet("The ablation was run twice and both runs are reported; only the finding that "
              "held across both is claimed.")
    dl.bullet("The timing correction is documented next to the table it corrects.")
    dl.bullet("requirements.txt was added with versions verified on the machine the results "
              "were produced on, and pythainlp is documented as non-optional.")
    dl.bullet("Results state the hardware and the exact switch settings they were produced "
              "under, because on this machine torch runs on CPU and Ollama on the GPU - a "
              "number without that context is not reproducible.")
    print()
    dl.para("Still open: detecting a refusal in query_transform.py and falling back to the "
            "original query would remove failure 1 at the source. It is a small change and it "
            "was not made, because it would invalidate the committed ablation numbers without "
            "an LLM run available to regenerate them.")
    print()
    dl.para("Source: LAB3/RAG-Project/evaluation/eval_query_transform.py, "
            "LAB3/RAG-Project/src/query_transform.py, LAB3/README.md")


if __name__ == "__main__":
    run()
