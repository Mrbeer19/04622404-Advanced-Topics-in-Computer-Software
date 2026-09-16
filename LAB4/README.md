# LAB4 — DL-05 RAG System Development II

> Thai edition: [`README.th.md`](README.th.md)

Ten problems found while building LAB1, LAB2 and LAB3, each one reproduced as runnable code against
the artefacts those labs actually produced.

Course structure from
[aproot-en/Advanced-Topic-in-Computer-Software-Course](https://github.com/aproot-en/Advanced-Topic-in-Computer-Software-Course/tree/main/DL-05-RAG%20System%20Development%20II).

## What this lab is

DL-05 asks for the problems that show up in an LLM/RAG system and how each one is handled. The course
template answers that with nine self-contained simulations: a `bad_generate()` that returns a
hard-coded lie, a noisy string built two lines before it is cleaned, a hypothetical document "at rank
8". They demonstrate the concepts clearly, and none of them can fail, because the failure is written
into the script.

This folder answers the same question with the problems that actually happened. Every module here is
a defect or a measurement from LAB1–LAB3 — a bug that broke something, a number that came out against
expectation, or a result that turned out to be measuring the wrong thing — reproduced so it can be
run, with the fix next to it.

| | Template | Here |
|---|---|---|
| Data | `sex_q_a.txt`, copied into the folder | `LAB3/RAG-Project/data/scam_q_a.txt`, read in place — one copy in the repository |
| Failures | written by hand inside the demo | taken from LAB1–LAB3, reproduced from the code that had them |
| Numbers | narrated in prose | loaded from the committed `eval_*.json` that produced them |
| Problems | 9 (`main.py` imports a 10th that is not in the repository) | 10, all present, all runnable |

## Running it

```bash
cd LAB4
python main.py          # menu
python main.py 7        # one problem
python main.py 0        # all ten, about 1000 lines
```

Standard library only. No LLM, no GPU, no model download, no `pip install` — the measured numbers are
read from the JSON that LAB3 wrote, not recomputed. Python 3.9 or newer.

`data_loader.py` resolves the LAB1 and LAB3 artefacts by relative path, so LAB4 has to sit next to
them in this repository. A missing artefact raises `MissingArtefact` with the command that produces
it, rather than a `FileNotFoundError` on a path nobody recognises.

## The ten problems

| # | Problem | From | What actually went wrong |
|---|---|---|---|
| 1 | [Hallucination and the silent fallback](problem01_hallucination.py) | LAB3 | A non-ASCII placeholder API key made every LLM call raise `UnicodeEncodeError`; a blanket `except` returned retrieved text as if it were generated, with the warning commented out |
| 2 | [Vocabulary mismatch / token position](problem02_transformer.py) | LAB2, LAB3 | Dense retrieval scored its **worst MRR anywhere** on slang — the queries it was supposed to be good at |
| 3 | [Data quality](problem03_data_quality.py) | LAB1, LAB4 | A parser that skipped blocks silently; four sources with two incompatible kinds of id; **five near-duplicate pairs found in the knowledge base by this lab** |
| 4 | [Chunk size, overlap, traceability](problem04_chunking.py) | LAB1, LAB2, LAB3 | Splitting by character position drops the question prefix from every tail chunk — 13 of them, 54–104 characters each |
| 5 | [Metadata filtering and index drift](problem05_metadata.py) | LAB3 | Retrieval reads the index, never the source file, so editing the knowledge base leaves the system answering from old data with no error |
| 6 | [Top-k and re-ranking](problem06_reranking.py) | LAB3 | +6.3 % MRR at **323× the latency**, and `hit@10` does not move at all — the switch has since flipped from `False` to `True`, and the module reads the live value rather than asserting one |
| 7 | [Retrieval correct, generation wrong](problem07_generation.py) | LAB3 | `NoLLM` split a Thai prompt on English markers, so `USE_LLM = False` refused **every** question; the real model still refuses 10 % with the answer in front of it |
| 8 | [Configuration](problem08_config.py) | LAB3 | `SHOW_SOURCES` was declared, documented, and read by nothing — the block that used it was commented out |
| 9 | [Evaluating the evaluation](problem09_evaluation.py) | LAB3 | `all_misses = misses` overwrote the diagnostic every round; the golden set derives its queries from its own answers, which is why BM25 "wins" at 0.9933 |
| 10 | [Reproducibility](problem10_reproducibility.py) | LAB3 | 26 % of HyDE prompts came back as refusals **and were sent to the retriever as search queries**; two identical runs differed by 4.6× the effect being measured |

## Three findings worth reading first

**A silent fallback is worse than a hallucination** (problem 01). The Ollama placeholder key was the
literal `"ollama-ไม่ใช้-key"`. That goes into the `Authorization` header, the OpenAI SDK encodes
headers as ASCII, and the call raised before it left the machine — every time. `Generator.generate()`
caught every exception, returned `chunks[0]["answer"]`, and its warning `print` was commented out. So
`USE_LLM = True` returned raw retrieved text while reporting itself as generation. A hallucination is
at least detectable. This was not.

**The benchmark was passable by construction** (problem 09). `build_golden_set.py` builds every query
variant from the target question by string operations — the `natural` variant is the question with
`สงสัยว่า` glued on the front and `ยังไงคะ` on the back. Measured here: the variants retain 92–100 % of
the target's characters. BM25 matches tokens, so it scores 0.9933 MRR and appears to beat a
568M-parameter cross-encoder. That is a fact about the benchmark, not about BM25.

**A safety-tuned model will not write a scam** (problem 10). HyDE asks the model to invent a plausible
answer, the knowledge base is about how scams work, and `llama3.1:8b` read that as a request for help
committing one. 18 of 68 prompts came back as an apology, and `query_transform.py` has no way to tell
an apology from an answer — so the apology went to the retriever as the search query. This is a real,
reproducible failure mode of HyDE on safety-sensitive material, and it is invisible unless you log
what was actually searched.

## Two defects this lab found on its own

Both were found by running a check rather than by assuming the data was clean, and both are reported
rather than patched:

- **Five near-duplicate pairs in `scam_q_a.txt`** (problem 03). In each one a slang-register variant
  was copied from the conversational one and edited by a word or two instead of being rewritten —
  questions 96.6–100 % identical, answers 96.2–100 % identical. An exact-match duplicate check finds
  one of the five. This matters beyond tidiness: the slang register is the variant that is supposed to
  test whether retrieval survives unfamiliar wording, and a "slang" query 97 % identical to its
  conversational twin does not test that at all.
- **Thirteen tail chunks with no question** (problem 04). `split_text()` cuts the combined
  `"Question: … Answer: …"` string by character position, so only the first piece keeps the question.
  Every tail chunk is a 54–104 character fragment embedded with no indication of what it answers.

Neither is patched here on purpose. Editing `scam_q_a.txt` or the splitter invalidates the committed
FAISS and BM25 indexes and every number in `outputs/` — which is exactly the failure mode problem 05
is about. The fix is to change the data and rebuild the index as one commit, with the evaluation
re-run; that needs the model stack that this folder deliberately does not depend on.

## Structure

```
LAB4/
├── data_loader.py                  shared parser + artefact loaders + report layout
├── main.py                         menu, or `python main.py <n>`
├── problem01_hallucination.py      hallucination, and the silent fallback
├── problem02_transformer.py        vocabulary mismatch, Thai tokenisation, position
├── problem03_data_quality.py       silent skips, id spaces, near-duplicates
├── problem04_chunking.py           chunk size, overlap, traceability
├── problem05_metadata.py           register filtering, index fingerprinting
├── problem06_reranking.py          two-stage retrieval and what it costs
├── problem07_generation.py         faithfulness, refusals, prompt/parser drift
├── problem08_config.py             switches, and checking each one is wired
├── problem09_evaluation.py         bugs in the measurement, leaks in the benchmark
├── problem10_reproducibility.py    LLM variance, refusals, timing noise, dependencies
├── README.md
└── README.th.md
```

`data_loader.py` does two things the template's does not. `load_qa_report()` returns the count and
reason for every block it skipped, so a knowledge base that half-parses cannot look like one that
parsed cleanly. And the LAB1/LAB3 artefacts are resolved by path instead of copied, so there is one
`scam_q_a.txt` in the repository and the numbers in this folder cannot drift away from the lab that
produced them.

## Where the numbers come from

Everything measured is read from files LAB3 committed, produced on Windows 11, Python 3.11.9, PyTorch
on CPU, Ollama on the GPU with `llama3.1:8b`:

| File | Used by |
|---|---|
| `LAB3/RAG-Project/outputs/eval_retrieval.json` | problems 2, 6, 9, 10 |
| `LAB3/RAG-Project/outputs/eval_query_transform.json` | problem 10 |
| `LAB3/RAG-Project/outputs/eval_generation.json` | problems 7, 9 |
| `LAB3/RAG-Project/outputs/chunks.json` | problem 4 |
| `LAB3/RAG-Project/data/golden_set.json` | problems 2, 9 |
| `LAB3/RAG-Project/vector_db/index_meta.json` | problem 5 |
| `LAB3/RAG-Project/config.py` | problems 6, 8 |
| `LAB1/Pipeline/outputs/chunked_*.json` | problems 3, 4 |
| `LAB1/Pipeline/outputs/boilerplate_lines.json` | problem 3 |

Full result tables and the LAB3 fix list: [`../LAB3/README.md`](../LAB3/README.md)
