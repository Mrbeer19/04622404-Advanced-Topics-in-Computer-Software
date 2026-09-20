# 04622404 Advanced-Topics-in-Computer-Software

This repository contains lab exercises, source code, assignments, projects, and additional learning resources.

## Course Description 

**New academic study in computer software.**

The course follows the official course description and extends it with modern AI topics such as **LLM**, **RAG** and **Agentic AI**. It also includes hands-on labs, projects, and real-world applications. The complete list of topics is available in the **Course Contents** section.

## Owner Information
- 116730462033-5 Prapakorn Phithamma
- Computer Engineering Department, Engineering Faculty, RMUTT

## Team Repository
- LAB 1 — LLM data pipeline: https://github.com/Automatic28m/Advance-AI-RAG
- LAB 5 — Travel safety assistant (8-person build): https://github.com/PROxTAE/travel-safety-ai

## Course Work

| LAB | Work | My part | Folder |
|---|---|---|---|
| 1 | LLM data pipeline (team project) | Chunking, stage 3 of the pipeline | [`LAB1/`](LAB1/) |
| 2 | DL-03 LLM Retrieval System (RAG) | Whole project: chunking, embeddings, FAISS vector database, retrieval | [`LAB2/`](LAB2/) |
| 3 | DL-04 RAG System Development I | Whole project: hybrid retrieval, reranking, generation, evaluation | [`LAB3/`](LAB3/) |
| 4 | DL-05 RAG System Development II | Whole project: the ten problems found across LAB1–LAB3, reproduced and fixed | [`LAB4/`](LAB4/) |
| 5 | DL-07 Agentic AI System II (team project) | Module 04 External Data Services: every provider the system reads from | [`LAB5/`](LAB5/) |

### LAB 1 — Chunking (LLM data pipeline)

Stage 3 of a team pipeline built in
[Automatic28m/Advance-AI-RAG](https://github.com/Automatic28m/Advance-AI-RAG): splits cleaned job
postings into chunks for the embedding stage. Three strategies selected by parameter (fixed-size with
overlap, paragraph, heading), token counting with `tiktoken` `cl100k_base`, and 518 chunks produced
from 180 postings. Every chunk carries the id of its source posting together with its source file, so
a chunk can always be traced back to the posting it came from.

Collection and Cleaning in that folder are teammates' work, used as input.

### LAB 2 — DL-03 LLM Retrieval System (RAG)

A complete retrieval pipeline written from scratch over a Thai personal-finance knowledge base of 388
question/answer pairs: chunking into 523 chunks, multilingual embeddings
(`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions), a FAISS index searched by cosine
similarity, and top-k semantic retrieval, laid out as labs 01–07 plus reusable modules.

### LAB 3 — DL-04 RAG System Development I

The retrieval pipeline from LAB 2 built out into a complete RAG system: BM25 keyword search fused
with dense retrieval through Reciprocal Rank Fusion, cross-encoder reranking, query transformation
(rewrite / multi-query / HyDE), LLM answer generation with inline citations, and conversation memory
— every stage switchable in `config.py` so its contribution can be measured.

The knowledge base is written for this lab: **391 Thai question/answer pairs on online scams,
phishing and personal cyber-security** (404 chunks), covering phishing links, call-centre gangs,
passwords and 2FA, money-draining apps, investment scams, and Thai-specific recourse — the 1441
hotline, online police reporting, and mule-account liability. Every subject is written in three
registers (formal, conversational, slang), which is what makes the retrieval comparison meaningful.

The evaluation module implements Hit@k, Recall@k, Precision@k, MRR and nDCG@k from scratch and scores
each retrieval configuration against a golden set of 54 items in four query styles. Hybrid retrieval
beats dense-only on every variant, and by the widest margin exactly where it should: on slang queries
MRR goes from 0.7083 to 0.9429, a 33 % gain, while hit@10 reaches a perfect 1.0000. Cross-encoder
reranking adds another 6.3 % MRR on top of that and leaves hit@10 untouched — the exact shape the
course notes predict, since a reranker can only reorder what retrieval already found — but it costs
323x the latency, which is why it stays off by default. Answer generation with `llama3.1:8b` retrieves
the correct chunk 100 % of the time and cites a source in every answer it writes.

Two results came out against expectation and are reported as measured. All three query-transformation
modes scored *below* leaving the switch off, partly because the model refused 26 % of the HyDE
prompts — it reads "invent a plausible answer describing a scam" as a request for help committing one
— and the refusal text then goes to the retriever as a search query. And BM25 alone scoring 0.9933
turned out to expose a leak in how the golden set is generated rather than a strength of the method.
Five defects in the course code were found and fixed along the way: the most serious made the no-LLM
mode refuse every question, and the most dangerous put Thai characters in an HTTP header so that every
LLM call failed and silently fell back to returning retrieved text as if it were a generated answer.

Details, full result tables and the fix list: [`LAB3/README.md`](LAB3/README.md)

### LAB 4 — DL-05 RAG System Development II

The ten problems that came out of building the three labs above, each one reproduced as runnable code
against the artefacts those labs actually produced — not simulated. Where the course template
demonstrates hallucination with a `bad_generate()` that returns a hard-coded lie, this folder
reproduces the defect that shipped instead: a placeholder API key containing Thai characters, which
the HTTP layer encodes as ASCII, so every LLM call raised before it left the machine and a blanket
`except` returned retrieved text as if it were generated — with the warning commented out. A
hallucination is detectable; that was not.

Each module states where the problem came from, reproduces the broken behaviour and the fixed one
side by side, and reports the measurement that settled it, loaded from the `eval_*.json` files LAB3
committed rather than restated from memory. Standard library only — no LLM, no GPU, no downloads.

Three that are worth reading on their own. **BM25 scoring 0.9933 MRR is a fact about the benchmark,
not about BM25**: every golden-set query variant is built from the target question by string
operations, and measurement here puts the character overlap at 92–100 %, so the test is one of
lightly edited copies. **A safety-tuned model will not write a scam**: 26 % of HyDE prompts came back
as an apology, and since nothing distinguished an apology from an answer, the apology went to the
retriever as the search query. **Two identical runs of the query-transform ablation differed by 4.6×
the effect being measured**, which is why only the direction of that result is claimed.

Running the checks also turned up two defects nobody was looking for: five near-duplicate pairs in
`scam_q_a.txt`, where a slang variant was copied from the conversational one and edited by a word
rather than rewritten, and thirteen chunks whose text is a 54–104 character fragment with the question
prefix cut off by the splitter. Both are reported rather than patched, because changing the data or
the splitter invalidates the committed index and every number in `outputs/` — which is the failure
mode problem 05 is about.

Details and the full problem list: [`LAB4/README.md`](LAB4/README.md)

### LAB 5 — DL-07 Agentic AI System II

Module 04 of an eight-person build,
[PROxTAE/travel-safety-ai](https://github.com/PROxTAE/travel-safety-ai): a travel safety
assistant that answers questions about a journey from live weather, hazard, routing and
transit data. This module is the one that talks to the outside world — every fact the
other seven modules reason about enters the system through it, so nothing downstream can
be more truthful than what it hands over.

Eight endpoints over nine registered providers: Open-Meteo geocoding and forecast, USGS,
GDACS and NASA EONET for hazards, openrouteservice for road routes and emergency places,
and a GTFS-Realtime transit feed — plus a combined endpoint that fans out to all of them
in parallel under one deadline and reports what each one managed to answer. All eight
phases of the module plan are delivered and merged, with 645 tests and 28 canaries that
call the real providers.

The module is built around one rule: **it never decides that anything is safe.**
`severity` is UNKNOWN on every hazard and `risk_level` is UNKNOWN on every route — not
because the information is missing, since the provider's own numbers are all carried
through, but because turning a magnitude into a danger level is a judgement that belongs
to a later module. An empty list always means "nothing was reported" and never "we could
not find out"; when every hazard source times out the request fails with an error code,
because `events: []` reads as *no hazards near you*.

Five defects worth reading about, each of which produced output that looked completely
healthy. **A GTFS realtime feed and its own timetable use different trip ids** — joining
them the obvious way matched zero of sixty-seven live trips and returned sixty-six
valid-looking records that all said UNKNOWN, with a 200 status. **GTFS clock times are
local to the agency**, so reading a New York timetable as UTC made every train exactly
250 minutes late. **Freshness was measuring the age of the earthquake rather than the
age of the data**, which marked 268 of 268 events STALE and none FRESH — and the entire
346-test suite passed while that was true, because nothing asserted what the field
*meant*, only that it was populated. **`official` was true on every record**, including
a magnitude -0.48 earthquake nobody can feel. And **a plausible-looking category id**
answered a "nearest hospital" search with a pub 250 m away.

Two findings changed the team's shared contract rather than this module. The schema
required every route to carry a risk assessment, which the producer cannot have made —
the only way to satisfy it was to assert that a route across a closed bridge was fine.
And it required every emergency place to have a name, while two of nineteen real
hospitals near Victory Monument have none in OpenStreetMap, one of them 335 m away and
nearer than several that do; the choice it left was to hide the closest hospital or
invent a label. Both are nullable now, the second with a conditional rule so that
"not yet assessed" cannot be read as "checked, and fine".

Details, the full acceptance checklist and all seventeen known limitations:
[`LAB5/README.md`](LAB5/README.md)
