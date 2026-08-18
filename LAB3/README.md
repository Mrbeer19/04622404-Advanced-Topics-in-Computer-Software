# LAB3 — DL-04 RAG System Development I

A full RAG system over a Thai online-scam awareness knowledge base: hybrid retrieval (BM25 + dense
with RRF), cross-encoder reranking, query transformation, LLM answer generation with citations,
conversation memory, and a retrieval evaluation suite with metrics written from scratch.

Course structure from
[aproot-en/Advanced-Topic-in-Computer-Software-Course](https://github.com/aproot-en/Advanced-Topic-in-Computer-Software-Course/tree/main/DL-04-RAG%20System%20Development%20I).
The knowledge base is written for this lab — see [Knowledge base](#knowledge-base).

## What is new since LAB2

LAB2 (DL-03) ended at dense retrieval. Everything below that line is new here.

| Stage | Modules | Status in LAB2 |
|---|---|---|
| **Stage 1** — core pipeline | `document_loader`, `text_splitter`, `embedding_model`, `vector_store`, `retriever` | same as LAB2 |
| **Stage 2** — retrieval quality | `hybrid_retriever` (BM25 + RRF), `rerankers` (cross-encoder), `query_transform` (rewrite / multi-query / HyDE), `index_meta` | new |
| **Stage 2** — generation | `prompt_templates`, `generator` (Ollama / OpenAI / Gemini), `memory`, `rag_pipeline` | new |
| **Stage 2** — evaluation | `metrics`, `build_golden_set`, `eval_retrieval`, `eval_generation` | new |

## Pipeline

```
scam_q_a.txt  ->  extracted_text.json  ->  chunks.json  ->  embeddings.npy  ->  document.index
 knowledge base      lab01 extract          lab02 chunk      lab03 embed        lab04 vector DB
                                                                          +->  bm25_index.pkl

query -> query_transform -> hybrid retrieval -> rerank -> generator -> answer + [n] citations
         rewrite/multi/HyDE   BM25 + dense + RRF   cross-encoder   LLM        memory keeps the thread
```

Every arrow after `query` is a switch in `config.py`, so a configuration can be turned off and
measured rather than argued about.

## Structure

```
LAB3/
└── RAG-Project/
    ├── data/
    │   ├── scam_q_a.txt             391 Thai Q&A pairs, the knowledge base
    │   └── golden_set.json          54 evaluation items, up to 4 query variants each
    ├── outputs/
    │   ├── extracted_text.json      parsed Q&A pairs with source line numbers
    │   ├── chunks.json              404 chunks with metadata
    │   ├── embeddings.npy           (404, 384) float32
    │   ├── retrieval_results.json   top-k results for the lab07 sample queries
    │   └── eval_retrieval.json      retrieval scores per configuration
    ├── vector_db/
    │   ├── document.index           FAISS index — dense semantic search
    │   ├── bm25_index.pkl           BM25 index — exact-token search
    │   ├── chunk_store.json         chunks aligned with FAISS order
    │   └── index_meta.json          fingerprint of the dataset the index was built from
    ├── labs/                        lab01–lab07, the step-by-step core pipeline
    ├── src/                         reusable modules (see the table above)
    ├── evaluation/                  metrics, golden set builder, two eval scripts
    ├── config.py                    every switch and path
    ├── build_index.py               builds FAISS + BM25 + metadata in one run
    ├── main.py                      interactive question answering
    └── requirements.txt
```

## Knowledge base

`data/scam_q_a.txt` — **391 Thai question/answer pairs** on online scams, phishing, and personal
cyber-security, written for this project. Split into **404 chunks** (`CHUNK_SIZE` 400 characters,
50-character overlap; only long answers split).

| Subject | Q&A pairs |
|---|---|
| Phishing and malicious links | 157 |
| Call-centre gangs and phone scams | 85 |
| Accounts, passwords, and authentication | 73 |
| Law and what to do after being scammed | 39 |
| Malware, money-draining apps, device security | 22 |
| Investment and crypto scams | 15 |

Every subject is written in **three registers**, because retrieval quality is exactly what this
difference tests:

| Register | Pairs | Example question |
|---|---|---|
| formal | 180 | `กดลิงก์ปลอมไปแล้วต้องทำอย่างไร` |
| conversational | 109 | `เผลอกดลิงก์ในเอสเอ็มเอสไปแล้ว ซวยไหม` |
| slang | 102 | `กูเผลอกดลิงก์เหี้ยนั่นไปแล้ว ตายป่ะ` |

The three registers carry the same facts in different words, so a question typed the way people
actually type it still has to reach the right answer. This is what separates a keyword matcher from
a retriever — and the evaluation below shows it does.

Thai-specific content is deliberate: the 1441 hotline, online police reporting, mule-account
(บัญชีม้า) liability, and the emergency-account-freeze powers under the 2023 cyber-crime decree.

## Feature switches

All in `config.py`, all measurable through `evaluation/`:

| Switch | Default | Effect |
|---|---|---|
| `USE_HYBRID` | `True` | BM25 alongside dense retrieval, merged with RRF |
| `USE_RERANK` | `False` | cross-encoder `BAAI/bge-reranker-v2-m3` reorders the top `CANDIDATE_K` |
| `USE_QUERY_TRANSFORM` | `False` | LLM rewrites / expands the query before retrieval |
| `USE_MEMORY` | `True` | conversation history for follow-up questions |
| `USE_LLM` | `True` | `False` returns retrieved text instead of a generated answer |
| `SHOW_SOURCES` | `False` | print the `[n]` source list under the answer |
| `SHOW_DEBUG` | `False` | print the queries actually searched and per-stage timings |

## Fixes applied to the course code

Four defects were found while getting the project to run. All four are fixed in this folder.

| File | Defect | Fix |
|---|---|---|
| `src/generator.py` | `NoLLM` split the prompt on the English markers `"reference data :"` and `"Q of user"`, but `USER_PROMPT` is written in Thai. Neither marker was ever found, so **`USE_LLM = False` answered `"ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"` to every question** and `eval_generation` scored a 100 % refusal rate | the two headers are now the constants `CONTEXT_HEADER` / `QUESTION_HEADER` in `prompt_templates.py`, used by both the prompt and the parser, so they cannot drift apart again |
| `main.py` | the block printing the source list was commented out, leaving `SHOW_SOURCES` with nothing to do; `rag.show_settings()` was commented out too | both restored |
| `evaluation/eval_retrieval.py` | `all_misses = misses` inside the configuration loop overwrote the list each round, so the "not retrieved" report only ever showed the last configuration | changed to accumulate, and each row now carries the configuration name |
| — | no `requirements.txt` in this lesson (DL-03 had one) | added, with versions verified on this machine |

Retargeting the project to this knowledge base also meant updating everything that was tied to the
original subject: `SOURCE_FILE` and `DISCLAIMER` in `config.py`, `SYSTEM_PROMPT` / `REWRITE_PROMPT` /
`HYDE_PROMPT` in `prompt_templates.py`, `SLANG_MAP` in `query_transform.py`, `TO_SLANG` in
`build_golden_set.py`, and the sample queries in labs 05–07.

## Running it

```bash
cd RAG-Project
pip install -r requirements.txt

python build_index.py                      # FAISS + BM25 + metadata, ~18 s
python main.py                             # ask questions interactively

python -m evaluation.metrics               # self-test of the metric formulas
python -m evaluation.build_golden_set      # regenerate the evaluation set
python -m evaluation.eval_retrieval        # compare retrieval configurations
python -m evaluation.eval_generation       # answer quality — needs an LLM
```

`pythainlp` is not optional. Without it `tokenize_thai()` falls back to sliding 3-character windows
and BM25 scores collapse, which would make the whole comparison meaningless.

Answer generation defaults to Ollama at `localhost:11434` with `llama3.1:8b`. Set `LLM_PROVIDER` to
`openai` or `gemini` in `config.py` (with the matching API key in the environment) to use a hosted
model instead. Retrieval evaluation needs no LLM at all.

## Results

`python -m evaluation.eval_retrieval`, 54 golden-set items × up to 4 query variants,
`USE_RERANK = False`:

| run | hit@1 | hit@10 | MRR | nDCG@3 | ms/query |
|---|---|---|---|---|---|
| dense_only | 0.7133 | 0.9867 | 0.8272 | 0.8390 | 11.9 |
| bm25_only | 0.9867 | 1.0000 | 0.9933 | 0.9951 | 2.2 |
| hybrid | 0.8200 | 1.0000 | 0.9063 | 0.9148 | 7.9 |

Per query variant (MRR):

| run | verbatim | slang | partial | natural |
|---|---|---|---|---|
| dense_only | 0.8568 | 0.7083 | 0.8405 | 0.8216 |
| bm25_only | 1.0000 | 1.0000 | 0.9821 | 0.9907 |
| hybrid | 0.9167 | **0.9429** | 0.8750 | 0.9028 |

Reading these numbers:

- **Hybrid beats dense-only on every single variant, and the gap is widest exactly where it should
  be.** On slang queries dense-only drops to 0.7083 MRR — its worst score anywhere — while hybrid
  holds 0.9429, a **+33 %** improvement. Slang is where a semantic model has no shared vocabulary to
  work with and keyword matching rescues the query, which is the behaviour the course notes predict.
- **hit@10 goes from 0.9867 to a perfect 1.0000** once BM25 is in the mix: with hybrid retrieval the
  correct chunk never falls out of the candidate set, so reranking has something to work with on
  every query.
- **Hybrid costs 7.9 ms per query against dense-only's 11.9 ms** — it is both better and faster here,
  because BM25 (2.2 ms) is cheap and the dense search dominates the cost either way.
- **BM25 alone scoring 0.9933 is not a result, it is a warning.** See below.

### The golden set leaks its answers

`build_golden_set.py` derives every query variant from the original question by string operations, so
each variant keeps most of the original wording:

| variant | items | how it is built |
|---|---|---|
| verbatim | 54 | the question itself |
| natural | 54 | `สงสัยว่า` + the same question + ` ยังไงคะ` |
| partial | 28 | the same question with stopwords dropped |
| slang | 14 | medical/technical terms swapped via the `TO_SLANG` table |

BM25 matches tokens, and nearly every token of the target is still present in the query, so it
retrieves the right chunk first almost every time. The `natural` variant — the one the course notes
call the deciding case — is the original question with a prefix and a suffix glued on, which changes
nothing for a bag-of-words scorer.

So the BM25 column measures how well a method handles *lightly edited copies of the target*, not real
user phrasing. The dense and hybrid columns are still informative relative to each other, and the
slang variant is the one place where the test has real teeth — which is why the dense-vs-hybrid gap
opens up there. Making the whole benchmark honest would need paraphrases that share intent but not
vocabulary, which means hand-written queries or an LLM generating them, plus a manual check, because
an LLM paraphrase can silently change the question.

### Not yet measured

| Configuration | Blocked by |
|---|---|
| `USE_RERANK = True` (adds a `hybrid+rerank` row) | a 2.2 GB download of `BAAI/bge-reranker-v2-m3` |
| `USE_QUERY_TRANSFORM = True` (rewrite / multi-query / HyDE) | needs a running LLM |
| `eval_generation` — faithfulness, correctness, citation rate | needs a running LLM |

The code path for all three was exercised: `get_reranker()` degrades to `None` instead of crashing
when the model cannot load, and `eval_generation` runs end to end with `USE_LLM = False` (0 %
refusal, 100 % citation rate, 0.16 s per question — which only confirms the plumbing works, since
those answers are retrieved text rather than generated text). `outputs/eval_generation.json` is
deliberately not committed: with `USE_LLM = False` its numbers describe extraction, not generation.

## Notes

- Answers are constrained to the knowledge base by `SYSTEM_PROMPT`, which requires inline `[n]`
  citations, mandates `"ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"` when the retrieved context is
  insufficient, and puts the urgent steps first when someone has just lost money. `DISCLAIMER` is
  appended to every answer.
- `index_meta.py` fingerprints the dataset and the chunking settings, and `main.py` warns when the
  index no longer matches what it was built from. Re-run `build_index.py` after touching the data or
  any `TRACKED_SETTINGS` value.
- The knowledge base is course material for studying retrieval. It is not legal advice, and hotline
  numbers and legal details should be checked against the current official sources before acting.
