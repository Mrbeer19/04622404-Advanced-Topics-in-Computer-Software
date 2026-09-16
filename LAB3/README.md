# LAB3 — DL-04 RAG System Development I

> Thai edition: [`README.th.md`](README.th.md)

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
    │   ├── eval_retrieval.json      retrieval scores per configuration
    │   ├── eval_query_transform.json  query-transform scores + every query searched
    │   └── eval_generation.json     answer-quality scores per question
    ├── vector_db/
    │   ├── document.index           FAISS index — dense semantic search
    │   ├── bm25_index.pkl           BM25 index — exact-token search
    │   ├── chunk_store.json         chunks aligned with FAISS order
    │   └── index_meta.json          fingerprint of the dataset the index was built from
    ├── labs/                        lab01–lab07, the step-by-step core pipeline
    ├── src/                         reusable modules (see the table above)
    ├── evaluation/                  metrics, golden set builder, three eval scripts
    ├── web/                         browser UI — index.html, app.js, style.css, bot avatar
    ├── config.py                    every switch and path
    ├── build_index.py               builds FAISS + BM25 + metadata in one run
    ├── main.py                      interactive question answering
    ├── api.py                       FastAPI server putting the pipeline behind HTTP
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
| `USE_RERANK` | `True` | cross-encoder `BAAI/bge-reranker-v2-m3` reorders the top `CANDIDATE_K`. Measured: **+6.3 % MRR at 323× the latency on CPU** |
| `USE_QUERY_TRANSFORM` | `False` | LLM rewrites / expands the query before retrieval. Measured: **every mode scored below leaving it off** |
| `USE_MEMORY` | `True` | conversation history for follow-up questions |
| `USE_LLM` | `True` | `False` returns retrieved text instead of a generated answer |
| `SHOW_SOURCES` | `False` | print the `[n]` source list under the answer |
| `SHOW_DEBUG` | `False` | print the queries actually searched and per-stage timings |

## Fixes applied to the course code

Five defects were found while getting the project to run. All five are fixed in this folder.

| File | Defect | Fix |
|---|---|---|
| `src/generator.py` | `NoLLM` split the prompt on the English markers `"reference data :"` and `"Q of user"`, but `USER_PROMPT` is written in Thai. Neither marker was ever found, so **`USE_LLM = False` answered `"ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"` to every question** and `eval_generation` scored a 100 % refusal rate | the two headers are now the constants `CONTEXT_HEADER` / `QUESTION_HEADER` in `prompt_templates.py`, used by both the prompt and the parser, so they cannot drift apart again |
| `main.py` | the block printing the source list was commented out, leaving `SHOW_SOURCES` with nothing to do; `rag.show_settings()` was commented out too | both restored |
| `evaluation/eval_retrieval.py` | `all_misses = misses` inside the configuration loop overwrote the list each round, so the "not retrieved" report only ever showed the last configuration | changed to accumulate, and each row now carries the configuration name |
| `src/generator.py` | the Ollama placeholder API key was the literal `"ollama-ไม่ใช้-key"`. That string goes into the `Authorization` header, which the OpenAI SDK encodes as ASCII, so **every LLM call raised `UnicodeEncodeError`**. `Generator.generate()` catches every exception and falls back to returning `chunks[0]["answer"]`, and its warning `print` was commented out — so `USE_LLM = True` returned retrieved text while reporting itself as generation, with nothing on screen to say so | placeholder is now ASCII (`"ollama-no-key"`), and the two `[llm]` log lines are uncommented so the fallback can never be silent again |
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
python api.py                              # web interface at http://127.0.0.1:8000

python -m evaluation.metrics               # self-test of the metric formulas
python -m evaluation.build_golden_set      # regenerate the evaluation set
python -m evaluation.eval_retrieval        # compare retrieval configurations
python -m evaluation.eval_query_transform  # compare transform modes — needs an LLM
python -m evaluation.eval_generation       # answer quality — needs an LLM
```

`pythainlp` is not optional. Without it `tokenize_thai()` falls back to sliding 3-character windows
and BM25 scores collapse, which would make the whole comparison meaningless.

Answer generation runs on **Gemini (`gemini-3.5-flash`)** through the OpenAI-compatible endpoint.
Copy `.env.example` to `.env` and put the key in it:

```
GOOGLE_API_KEY=your-key-here
```

`config.py` loads that file with `python-dotenv`, and `.env` is in `.gitignore` so the key never
reaches the repository. Set `LLM_PROVIDER` back to `ollama` for a local `llama3.1:8b` (no key
needed) or to `openai` with `OPENAI_API_KEY`. Retrieval evaluation needs no LLM at all.

## Web interface

`api.py` puts the pipeline that `main.py` already uses behind HTTP — there is no second RAG
implementation and no LLM call from the browser. FastAPI serves `web/` as static files and answers
three endpoints:

| Endpoint | What it does |
|---|---|
| `GET /api/health` | whether the model and index finished loading, the active LLM, and the live `config.py` switches |
| `POST /api/ask` | `{question, session_id}` -> `{answer, sources, no_context, answered_by, model, elapsed, timings}` through `RAGPipeline.ask()` |
| `POST /api/clear` | drops the server-side conversation memory of one session |

- **Models load once.** The FastAPI `lifespan` hook builds `RAGPipeline` at startup and
  `index_meta.warn_if_stale()` runs there, so a request never pays for loading and a stale index is
  reported before the first question.
- **One memory per browser, not per server.** `RAGPipeline` owns a single `ConversationMemory`, so
  the server keeps one per `session_id` and swaps it in under a lock. The session table is an LRU
  capped at `MAX_SESSIONS = 200`, so memory cannot grow without limit.
- **The LLM is called server-side only.** No API key reaches the browser, and questions are capped
  at `MAX_QUESTION_CHARS = 1000`. Every error — startup failure, bad input, LLM failure — comes back
  as the same `{"error": ...}` JSON shape.
- **Every answer says where it came from.** `answered_by` separates the four cases that all used to
  look alike on screen: `llm` (the model wrote it from retrieved context), `llm_refused` (retrieval
  found chunks but the model declined to answer), `no_context` (retrieval found nothing, so the
  system answered "I don't know" instead of letting the model guess), and `fallback_context` (the
  LLM call failed and the retrieved text is shown raw). The browser prints that, the model name, and
  the time split — total, search, and generation — as tags under each answer.
- **`web/` is plain HTML/CSS/JS, no build step.** Sample-question chips, the `[n]` source list under
  each answer, and a status line fed by `/api/health`.

The switches in `config.py` apply here exactly as they do on the command line — the web interface is
a front end for the same configuration, not a separate one.

## Results

Everything below was measured on one machine — Windows 11, Python 3.11.9, PyTorch on CPU
(`torch.cuda.is_available()` is `False` here), Ollama on the GPU, `llama3.1:8b` as the LLM. The
configuration measured was `USE_HYBRID = True`, rerank and query transform off, `USE_LLM = True`,
and each table states which switches were changed to produce it. The committed `config.py` has since
moved on — it now runs `USE_RERANK = True` on `gemini-3.5-flash` — so the numbers below describe the
switches, not the current default.

### Retrieval

`python -m evaluation.eval_retrieval`, 54 golden-set items x up to 4 query variants = 216 queries,
run with `USE_RERANK = True` so the fourth row appears. The first three rows came out identical to a
separate `USE_RERANK = False` run, so the reranker does not disturb the rows above it.

| run | hit@1 | hit@10 | MRR | nDCG@3 | ms/query |
|---|---|---|---|---|---|
| dense_only | 0.7133 | 0.9867 | 0.8272 | 0.8390 | 12.5 |
| bm25_only | 0.9867 | 1.0000 | 0.9933 | 0.9951 | 4.9 |
| hybrid | 0.8200 | 1.0000 | 0.9063 | 0.9148 | 12.5 |
| hybrid+rerank | 0.9267 | 1.0000 | **0.9633** | **0.9626** | 4035.5 |

Per query variant (MRR):

| run | verbatim | slang | partial | natural |
|---|---|---|---|---|
| dense_only | 0.8568 | 0.7083 | 0.8405 | 0.8216 |
| bm25_only | 1.0000 | 1.0000 | 0.9821 | 0.9907 |
| hybrid | 0.9167 | 0.9429 | 0.8750 | 0.9028 |
| hybrid+rerank | 0.9537 | **1.0000** | 0.9464 | 0.9722 |

Reading these numbers:

- **Hybrid beats dense-only on every single variant, and the gap is widest exactly where it should
  be.** On slang queries dense-only drops to 0.7083 MRR — its worst score anywhere — while hybrid
  holds 0.9429, a **+33 %** improvement. Slang is where a semantic model has no shared vocabulary to
  work with and keyword matching rescues the query, which is the behaviour the course notes predict.
- **hit@10 goes from 0.9867 to a perfect 1.0000** once BM25 is in the mix: with hybrid retrieval the
  correct chunk never falls out of the candidate set, so reranking has something to work with on
  every query.
- **Reranking behaves exactly the way the course notes say it should.** MRR 0.9063 -> 0.9633
  (+6.3 %), nDCG@3 0.9148 -> 0.9626 (+5.2 %), hit@1 0.8200 -> 0.9267 (+13.0 %) — and hit@10 does not
  move at all. A cross-encoder only reorders what retrieval already found; it cannot pull in a chunk
  that was missed, so it moves rank-sensitive metrics and leaves set-membership metrics alone. Here
  hit@10 was already saturated at 1.0000, so it had nowhere to go even in principle. Reranking also
  closes out the slang variant completely, 0.9429 -> 1.0000.
- **The reranker costs 4035.5 ms per query against hybrid's 12.5 ms — 323x slower.** It scores 20
  query-document pairs per query through a 568M-parameter cross-encoder (`BAAI/bge-reranker-v2-m3`),
  4320 pairs in total, on CPU. It is the most accurate configuration measured here and by far the
  slowest, so it is a deliberate trade: the committed config turns it on and accepts the wait. On
  the Mac used for the web interface a reranked search settles around 3–5 s, with the LLM adding a
  few seconds on top.
- **BM25 alone scoring 0.9933 is not a result, it is a warning.** See below.

A correction to the previous edition of this table: it reported hybrid at 7.9 ms/query against
dense-only's 11.9 ms and concluded that hybrid was both better *and* faster. Re-running put both at
12.5 ms. That was timing noise and the conclusion was wrong — hybrid does everything dense-only does
*and then* runs BM25, so it cannot be faster. BM25 costs 4.9 ms standalone, small enough next to the
dense search that the difference disappears into run-to-run variation.

### Query transformation

`eval_retrieval.py` calls the retriever directly and never runs the transform step, so it cannot
measure this switch at all. `evaluation/eval_query_transform.py` was written for it: it does what
`RAGPipeline.search_only()` does — transform the query, then search every query that comes back —
and records what was actually sent to the retriever.

54 items x {natural, slang} = 68 queries per mode, `llama3.1:8b` on Ollama, rerank off.
`none` is not "no processing": `normalize_query()` still applies the slang lookup table, which is
what the pipeline does whenever `USE_QUERY_TRANSFORM` is off.

| mode | hit@1 | hit@10 | MRR | nDCG@3 | ms/query | queries searched | LLM refusals |
|---|---|---|---|---|---|---|---|
| none | **0.8529** | 1.0000 | **0.9228** | **0.9251** | 25.0 | 1.00 | 0 |
| rewrite | 0.3529 | 0.8235 | 0.5364 | 0.5527 | 698.8 | 1.00 | 4 |
| multi_query | 0.7794 | 1.0000 | 0.8713 | 0.8739 | 2134.0 | 3.68 | 5 |
| hyde | 0.8088 | 1.0000 | 0.8881 | 0.8937 | 4414.0 | 2.00 | 18 |

Per query variant (MRR):

| mode | natural | slang |
|---|---|---|
| none | **0.9028** | **1.0000** |
| rewrite | 0.5774 | 0.3782 |
| multi_query | 0.8704 | 0.8750 |
| hyde | 0.8715 | 0.9524 |

**All three LLM modes scored below leaving the switch off** — rewrite -41.9 % MRR, multi_query
-5.6 %, hyde -3.8 %. The course notes expect the opposite. Three things are going on, and none of
them is "query transformation is a bad idea":

1. **The benchmark rewards keeping the original wording, and `rewrite` throws it away.** `rewrite`
   *replaces* the question with the LLM's phrasing — 69 % of the original length on average — while
   `multi_query` and `hyde` keep the original as the first query and only add to it. That ordering
   is exactly the ordering of the damage. A concrete case: `การหลอกให้โอนตังค์ไป "บัญชีปลอดภัย"
   คืออะไร` became `การหลอกลวงการโอนเงินไปยังบัญชีปลอม`, dropping `บัญชีปลอดภัย` — the exact term
   the target chunk is built around. Since the golden set derives its queries from the target text
   (see below), any rephrasing is a loss by construction.
2. **The model refuses.** `llama3.1:8b` is safety-tuned, the knowledge base is about how scams work,
   and asking it to invent a plausible answer describing a scam technique reads to it like a request
   for help committing one. **18 of 68 HyDE prompts (26 %) came back as an apology** rather than a
   hypothetical answer — `ขอโทษครับ/ค่ะ แต่ฉันไม่สามารถช่วยเขียนคำตอบที่อาจช่วยให้บุคคลหลอกลวง...` —
   and `query_transform.py` has no way to tell a refusal from an answer, so that apology goes to the
   retriever as a search query. `rewrite` (4) and `multi_query` (5) hit it less often but hit it.
   This is a real, reproducible failure mode of HyDE on a safety-sensitive knowledge base, and it is
   invisible unless you log what was searched.
3. **`normalize_query()` already did the job for free.** The lookup table maps ตังค์ -> เงิน,
   แบงก์ -> ธนาคาร, มิจ -> มิจฉาชีพ, which is precisely the slang-to-formal bridging the LLM was
   supposed to provide. On the slang variant `none` scores a perfect **1.0000** MRR. There was
   nothing left to gain and only wording to lose.

**These percentages are noisy — treat the direction, not the magnitude, as the finding.** The
ablation was run twice with identical code at `LLM_TEMPERATURE = 0.2`:

| mode | run 1 MRR | run 2 MRR |
|---|---|---|
| none | 0.9228 | 0.9228 |
| rewrite | 0.6130 | 0.5364 |
| multi_query | 0.8811 | 0.8713 |
| hyde | 0.8186 | 0.8881 |

`none` is deterministic and repeated exactly; every LLM mode moved — `rewrite` by 7.7 points and
`hyde` by 7.0, against a `hyde`-to-`multi_query` gap of 1.7. The run-to-run spread is over four
times the difference being measured, so one run of 68 queries cannot separate those two modes at
all. What held across both runs is the only claim made here: all three modes landed below `none`.
The committed numbers are run 2, whose transformed queries are all saved in
`outputs/eval_query_transform.json`.

### Generation

`python -m evaluation.eval_generation` with **`USE_LLM = True`** — 20 items, natural variant, hybrid
retrieval, no rerank, no query transform, `llama3.1:8b` on Ollama.

| metric | value |
|---|---|
| refusal rate | 0.10 |
| correct chunk retrieved | 1.00 |
| answer carries an `[n]` citation | 0.90 |
| faithfulness — answer words present in the retrieved context | 0.8216 |
| correctness — answer words present in the reference answer | 0.6152 |
| relevance — question words present in the answer | 0.4475 |
| seconds per question | 3.93 (range 0.8 – 9.8) |

Reading these numbers:

- **Retrieval never failed on this subset (1.00), so every number here is about generation alone.**
- **The 10 % refusal rate is a generation failure, not a retrieval one.** Both refused items had the
  correct chunk sitting in the context window and refused anyway. `g0068` asked
  `รหัส OTP คืออะไร ทำไมห้ามบอกใคร` and got back
  `ขออภัย ไม่พบข้อมูลที่เกี่ยวข้องเกี่ยวกับคำจำกัดความของ OTP` — with the definition of OTP in the
  prompt. An 8B model applying `SYSTEM_PROMPT`'s "say you do not know rather than guess" rule too
  eagerly is the likeliest explanation.
- **Citation rate 0.90 is exactly 1 − refusal rate.** Every answer that was actually written carried
  an inline `[n]`; the only two without one are the two refusals, which have nothing to cite. The
  citation instruction is followed 100 % of the time it applies.
- **Faithfulness 0.8216** says answers stay close to the retrieved text rather than drawing on the
  model's own knowledge, which is the property that matters for this knowledge base.
- **Correctness 0.6152 and relevance 0.4475 are word-overlap heuristics, not judgements.**
  `word_overlap()` counts how many tokens of one text appear in another, so an answer that is
  correct but worded differently from the reference scores low, and a thorough answer scores low on
  relevance for length rather than for being wrong. Read them as "did not drift", not as "was
  right". Grading correctness properly needs an LLM judge or a human reader, neither of which is in
  scope here.

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

### What these numbers do not cover

Every switch in `config.py` now has a measurement behind it. What is still missing is depth, not
coverage:

| Gap | Why it matters |
|---|---|
| `correctness` and `relevance` are token-overlap heuristics | they cannot tell a differently-worded correct answer from a wrong one. An LLM judge or a human reader would be needed to grade answer quality properly |
| generation was scored on 20 items, one variant, one run | enough to catch a broken pipeline, not enough to compare two prompts or two models |
| the query-transform ablation moved by up to 7.7 MRR points between two identical runs | single-run LLM numbers carry more noise than most of the differences being measured |
| only `llama3.1:8b` was tested | the 26 % HyDE refusal rate is a property of this model on this subject, not of HyDE |

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
