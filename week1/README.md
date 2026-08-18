# LAB1 — LLM Data Pipeline (team project)

This folder is a `git subtree` of my feature branch in the team repository
[Automatic28m/Advance-AI-RAG](https://github.com/Automatic28m/Advance-AI-RAG), so it holds the
whole pipeline as it stood at that point, not only my own stage.

## What is mine

**Stage 3 — Chunking**, by 116730462033-5 Prapakorn Phithamma.

| File | |
|---|---|
| [`Pipeline/chunking.py`](Pipeline/chunking.py) | the stage, written as functions that can be called on their own |
| [`Pipeline/03_data_chunking.py`](Pipeline/03_data_chunking.py) | runner over the real input, prints a sample and runs the checks |
| `Pipeline/outputs/chunked_*.json` | my output: 518 chunks from the 180 cleaned postings |

Run it with:

```bash
python Pipeline/03_data_chunking.py
python Pipeline/03_data_chunking.py --strategy fixed --max-tokens 300 --overlap 30
python Pipeline/03_data_chunking.py --heading-mode strict --no-pack
```

Three strategies, selected per call: `fixed` (token windows with overlap), `paragraph`, and
`heading` (sections cut on the short heading lines that the cleaning stage kept for this
purpose). Chunk size, overlap and the tokenizer encoding are arguments, not fixed values.
Token counting uses `tiktoken` `cl100k_base` so a chunk size means the same number the
embedding stage will measure.

Every chunk carries the `id` of the posting it came from together with its `source`, because
Jobicy identifies postings with ints and AIDevBoard with UUIDs: the two id spaces are
unrelated, so an id on its own cannot be resolved back to a posting. `chunk_index` runs
0..n-1 per posting so a posting can be reassembled in order.

## What came from the team

Used as input, not written by me:

| File | Stage | |
|---|---|---|
| [`Pipeline/01_data_collection.ipynb`](Pipeline/01_data_collection.ipynb) | 1 — Collection | produces `outputs/extracted_text_*.json` |
| [`Pipeline/cleaning.py`](Pipeline/cleaning.py), [`Pipeline/02_data_cleaning.py`](Pipeline/02_data_cleaning.py) | 2 — Cleaning + Normalization | produces `outputs/cleaned_*.json`, the input to my stage |
| [`LLM_data_processing.ipynb`](LLM_data_processing.ipynb) | — | earlier shared notebook |

So the chain in this folder reads:

```
extracted_text_*.json  ->  cleaned_*.json  ->  chunked_*.json
   stage 1 (team)          stage 2 (team)      stage 3 (mine)
```

## Team members

- 116730462006-1 Phanlop Boonluea
- 116730462011-1 Saran Tanyavikai
- 116730462016-0 Sakda Baokam
- 116730462032-7 Praphavit Kaorak
- 116730462033-5 Praphakorn Pitamma
- 116730462035-0 Pitchakorn Phuadkhunthod
