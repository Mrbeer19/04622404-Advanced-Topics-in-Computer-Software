# LAB3 — DL-04 RAG System Development I

A full RAG system over a Thai sexual-health knowledge base: hybrid retrieval (BM25 + dense with RRF),
cross-encoder reranking, query transformation, LLM answer generation with citations, conversation
memory, and a retrieval evaluation suite with metrics written from scratch.

Course material from
[aproot-en/Advanced-Topic-in-Computer-Software-Course](https://github.com/aproot-en/Advanced-Topic-in-Computer-Software-Course/tree/main/DL-04-RAG%20System%20Development%20I).

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
sex_q_a.txt  ->  extracted_text.json  ->  chunks.json  ->  embeddings.npy  ->  document.index
 knowledge base     lab01 extract          lab02 chunk      lab03 embed        lab04 vector DB
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
    │   ├── sex_q_a.txt              391 Thai Q&A pairs, the knowledge base
    │   └── golden_set.json          54 evaluation items, 4 query variants each
    ├── outputs/
    │   ├── extracted_text.json      parsed Q&A pairs with source line numbers
    │   ├── chunks.json              541 chunks with metadata
    │   ├── embeddings.npy           (541, 384) float32
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

`data/sex_q_a.txt` — **391 Thai question/answer pairs** on sexual health, split into **541 chunks**
(`CHUNK_SIZE` 400 characters, 50-character overlap; only long answers split).

| Subject | Q&A pairs |
|---|---|
| Sexual health and protection | 144 |
| Anatomy and sexual response | 90 |
| Consent and relationships | 79 |
| Law and Thai social context | 40 |
| Gender diversity and health | 22 |
| Fertility and family planning | 16 |

Each subject is written in three registers — formal, conversational and slang — so a question asked
casually still has to reach the right answer.

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

## Running it

```bash
cd RAG-Project
pip install -r requirements.txt

python build_index.py                      # FAISS + BM25 + metadata, ~18 s
python main.py                             # ask questions interactively

python -m evaluation.metrics               # self-test of the metric formulas
python -m evaluation.eval_retrieval        # compare retrieval configurations
python -m evaluation.eval_generation       # answer quality — needs an LLM
```

`pythainlp` is not optional. Without it `tokenize_thai()` falls back to sliding 3-character windows
and BM25 scores collapse, which would make the whole comparison meaningless.

Answer generation defaults to Ollama at `localhost:11434` with `llama3.1:8b`. Set `LLM_PROVIDER` to
`openai` or `gemini` in `config.py` (with the matching API key in the environment) to use a hosted
model instead. Retrieval evaluation needs no LLM at all.

## Results

`python -m evaluation.eval_retrieval`, 54 golden-set items × 4 query variants, `USE_RERANK = False`:

| run | hit@1 | hit@10 | MRR | nDCG@3 | ms/query |
|---|---|---|---|---|---|
| dense_only | 0.7929 | 0.9286 | 0.8445 | 0.7538 | 11.6 |
| bm25_only | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 2.5 |
| hybrid | 0.8643 | 1.0000 | 0.9219 | 0.8493 | 7.9 |

Per query variant (MRR):

| run | verbatim | slang | partial | natural |
|---|---|---|---|---|
| dense_only | 0.8580 | 0.7500 | 0.7833 | 0.8684 |
| bm25_only | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| hybrid | 0.9327 | 0.7500 | 0.8844 | 0.9383 |

Reading these numbers:

- **Hybrid beats dense on every variant except slang**, and the gain is largest on `partial`
  (0.7833 → 0.8844 MRR), which is the behaviour the course notes predict: keyword search rescues the
  queries where the sentence has been cut down to bare terms. It also lifts hit@10 to a perfect 1.0000,
  so nothing falls out of the candidate set.
- **dense_only is the only run that misses anything**, and it misses exactly where a dense model
  should struggle — slang with no shared vocabulary (`"ชอบเพศเดียวกัน รักษาให้หายได้ป่ะ"` retrieved
  chunk 485 instead of 536).
- **BM25 scoring a perfect 1.0000 on all four variants is not a result, it is a warning.** See below.

### The golden set leaks its answers

`build_golden_set.py` derives all four variants from the original question by string operations, so
every variant keeps the original wording:

| variant | example |
|---|---|
| verbatim | `การสวนล้างช่องคลอดช่วยทำความสะอาดหรือป้องกันโรคได้หรือไม่` |
| natural | `สงสัยว่า` + the same question + ` ยังไงคะ` |
| partial | the same question with stopwords dropped — for short questions, byte-identical to verbatim |
| slang | present on **2 of 54 items**; the other 52 contain no term in the substitution table |

BM25 matches tokens, and every token of the target is still in the query, so it retrieves the right
chunk first every single time. The `natural` variant — the one the course notes call the deciding
case — is the original question with a prefix and a suffix glued on, which changes nothing for a
bag-of-words scorer.

So the comparison measures how well each method handles *lightly edited copies of the target*, not
real user phrasing. The dense and hybrid numbers are still informative relative to each other; the
BM25 column is not. Making it a real test needs paraphrases that share intent but not vocabulary,
which means either hand-written queries or an LLM generating them — and the golden set would then
have to be checked by hand, because an LLM paraphrase can silently change the question.

### Not yet measured

| Configuration | Blocked by |
|---|---|
| `USE_RERANK = True` (adds a `hybrid+rerank` row) | a 2.2 GB download of `BAAI/bge-reranker-v2-m3` |
| `USE_QUERY_TRANSFORM = True` (rewrite / multi-query / HyDE) | needs a running LLM |
| `eval_generation` — faithfulness, correctness, citation rate | needs a running LLM |

The code path for all three was exercised: `get_reranker()` degrades to `None` instead of crashing
when the model cannot load, and `eval_generation` runs end to end with `USE_LLM = False` (5 items,
0 % refusal, 100 % citation rate, 0.16 s per question — which only confirms the plumbing works, since
those answers are retrieved text rather than generated text). `outputs/eval_generation.json` is
deliberately not committed: with `USE_LLM = False` its numbers describe extraction, not generation.

## Notes

- Answers are constrained to the knowledge base by `SYSTEM_PROMPT`, which requires inline `[n]`
  citations and mandates `"ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"` when the retrieved context is
  insufficient. `DISCLAIMER` is appended to every answer.
- `index_meta.py` fingerprints the dataset and the chunking settings, and `main.py` warns when the
  index no longer matches what it was built from. Re-run `build_index.py` after touching the data or
  any `TRACKED_SETTINGS` value.
- The knowledge base is course material for studying retrieval. It is not medical advice.
