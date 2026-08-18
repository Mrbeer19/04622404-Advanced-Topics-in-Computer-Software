# LAB2 — DL-03 LLM Retrieval System (RAG)

A retrieval-augmented generation pipeline built from scratch in Python: text extraction, chunking,
embeddings, a FAISS vector database, and semantic search over a Thai personal-finance knowledge base.

Source repository: [Mrbeer19/DL-03-LLM-Retrieval-System](https://github.com/Mrbeer19/DL-03-LLM-Retrieval-System),
pulled into this folder with `git subtree`.

## Pipeline

```
finance_q_a.txt  ->  extracted_text.json  ->  chunks.json  ->  embeddings.npy  ->  document.index
   knowledge base       lab01 extract         lab02 chunk      lab03 embed        lab04 vector DB

query  ->  query vector  ->  similarity search  ->  top-k chunks
           lab05             lab06                  lab07 / main.py
```

| Lab | File | Step |
|---|---|---|
| 01 | [`labs/lab01_extract_text.py`](RAG-Project/labs/lab01_extract_text.py) | read the knowledge base and keep line numbers |
| 02 | [`labs/lab02_chunking.py`](RAG-Project/labs/lab02_chunking.py) | split into chunks with metadata |
| 03 | [`labs/lab03_create_embeddings.py`](RAG-Project/labs/lab03_create_embeddings.py) | encode every chunk into a vector |
| 04 | [`labs/lab04_create_vector_db.py`](RAG-Project/labs/lab04_create_vector_db.py) | build and save the FAISS index |
| 05 | [`labs/lab05_query_embedding.py`](RAG-Project/labs/lab05_query_embedding.py) | encode a user query the same way |
| 06 | [`labs/lab06_similarity_search.py`](RAG-Project/labs/lab06_similarity_search.py) | retrieve the top-k nearest chunks |
| 07 | [`labs/lab07_complete_retrieval.py`](RAG-Project/labs/lab07_complete_retrieval.py) | the whole retrieval path end to end |

The reusable modules behind the labs live in [`RAG-Project/src/`](RAG-Project/src):
`document_loader.py`, `text_splitter.py`, `embedding_model.py`, `vector_store.py`, `retriever.py`.
Paths and constants are shared through [`RAG-Project/config.py`](RAG-Project/config.py) so no lab
hardcodes them.

## Knowledge base

`RAG-Project/data/finance_q_a.txt` — **388 Thai question/answer pairs** on personal finance, written
for this project. Six subject areas:

| Subject | Q&A pairs |
|---|---|
| Budgeting and financial planning basics | 144 |
| Investing and returns | 87 |
| Debt and credit | 75 |
| Tax and Thai financial law | 44 |
| Insurance and risk management | 22 |
| Retirement and long-term planning | 16 |

Each subject is written in three registers — formal, conversational and slang — so that a question
asked casually still retrieves the right answer, which is what retrieval quality turns on here.

## How it works

- **Chunking** — the data is already in Q&A form, so one pair is normally one chunk. An answer longer
  than `CHUNK_SIZE` (400 characters) is split further with a 50-character overlap, and the pieces keep
  `qa_id` and `part_idx` so they can be traced back to the pair they came from. Result: **523 chunks**
  from 388 pairs.
- **Embeddings** — `paraphrase-multilingual-MiniLM-L12-v2`, a multilingual model, because the corpus
  is Thai. Output is `embeddings.npy`, shape **(523, 384)** float32.
- **Vector database** — FAISS `IndexFlatIP`. Vectors are normalized when they are created, so inner
  product is cosine similarity and a higher score means a closer match.
- **Retrieval** — `Retriever` encodes the query with the same model, searches the index, and returns
  each matching chunk together with its score. `TOP_K` is 3 in the configuration; `main.py` shows the
  single best answer.

## Running it

```bash
cd RAG-Project
pip install -r requirements.txt

python labs/lab01_extract_text.py     # ... through lab04, to build the vector database
python main.py                        # then ask questions interactively
```

`main.py` needs `vector_db/document.index` and `vector_db/chunk_store.json`, so labs 01–04 have to run
first. Both files are committed here, along with the intermediate outputs in `RAG-Project/outputs/`,
so the retrieval side can be run without rebuilding anything.

## Notes

- Answers come only from the knowledge base. Nothing is generated, so the system cannot invent an
  answer it has no source for.
- The knowledge base is course material for studying retrieval, not financial advice.
