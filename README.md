# 04622404 Advanced-Topics-in-Computer-Software

This repository contains lab exercises, source code, assignments, projects, and additional learning resources.

## Course Description 

**New academic study in computer software.**

The course follows the official course description and extends it with modern AI topics such as **LLM**, **RAG** and **Agentic AI**. It also includes hands-on labs, projects, and real-world applications. The complete list of topics is available in the **Course Contents** section.

## Owner Information
- 116730462033-5 Prapakorn Phithamma
- Computer Engineering Department, Engineering Faculty, RMUTT

## Team Repository
- Please check out this repository for team project https://github.com/Automatic28m/Advance-AI-RAG

## Course Work

| LAB | Work | My part | Folder |
|---|---|---|---|
| 1 | LLM data pipeline (team project) | Chunking, stage 3 of the pipeline | [`LAB1/`](LAB1/) |
| 2 | DL-03 LLM Retrieval System (RAG) | Whole project: chunking, embeddings, FAISS vector database, retrieval | [`LAB2/`](LAB2/) |
| 3 | DL-04 RAG System Development I | Whole project: hybrid retrieval, reranking, generation, evaluation | [`LAB3/`](LAB3/) |

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
