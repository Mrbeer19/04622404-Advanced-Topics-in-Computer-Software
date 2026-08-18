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
| 1 | LLM data pipeline (team project) | Chunking, stage 3 of the pipeline | [`week1/`](week1/) |
| 2 | DL-03 LLM Retrieval System (RAG) | Whole project: chunking, embeddings, FAISS vector database, retrieval | [`week2/`](week2/) |

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
