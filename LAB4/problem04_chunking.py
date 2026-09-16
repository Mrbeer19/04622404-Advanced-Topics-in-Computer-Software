# -*- coding: utf-8 -*-
"""Problem 04 - Chunk size, overlap, and the boundary you are allowed to cut on.

Where it came from
    LAB1 (DL-02) stage 3, chunking scraped job postings.
    LAB2 (DL-03) and LAB3 (DL-04), chunking a Q&A knowledge base.

The course template splits a document into fixed windows of N whitespace tokens
and shows that a large window mixes topics while a small one cuts sentences in
half. Both are true. But the template also demonstrates the trap it is warning
about: it builds its sample document by concatenating every answer in a category
into one string, so the Q&A boundaries - the only structure the data has - are
destroyed before chunking even starts.

The two real projects both ended up rejecting fixed-size windows as the primary
strategy, for the same reason and with different answers:

  LAB1  job postings have headings. `strategy="heading"` cuts on them and packs
        sections up to a token budget; fixed windows are the fallback.
  LAB2  a Q&A pair is already the right unit. One pair is one chunk, and only an
        answer longer than CHUNK_SIZE gets split further, with overlap.
  LAB3  same rule, and the split pieces keep qa_id and part_idx so a chunk can
        always be traced back to the pair it came from.

This module measures what those decisions produced, and what the naive split
would have produced on the same data.
"""

import collections

import data_loader as dl


def longest_seam(left, right):
    """The longest suffix of `left` that is also a prefix of `right`."""
    for size in range(min(len(left), len(right)), 0, -1):
        if left.endswith(right[:size]):
            return right[:size]
    return ""


def fixed_chunks(text, size, overlap=0):
    """The template's strategy: fixed character windows, ignoring structure."""
    step = max(1, size - overlap)
    return [text[i:i + size] for i in range(0, len(text), step)]


def run():
    entries = dl.load_qa()

    dl.title("PROBLEM 04  Chunk size / overlap")

    dl.section("A. what LAB3 actually produced")
    try:
        chunks = dl.chunks()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    per_pair = collections.Counter(chunk["qa_id"] for chunk in chunks)
    split_pairs = {qa_id: count for qa_id, count in per_pair.items() if count > 1}
    embedded = [len(chunk["text"]) for chunk in chunks]

    dl.kv("Q&A pairs in the knowledge base", len(entries))
    dl.kv("chunks produced", len(chunks))
    dl.kv("pairs that fit in one chunk", len(per_pair) - len(split_pairs))
    dl.kv("pairs split because the text was long", len(split_pairs))
    dl.kv("most parts any one pair became", max(per_pair.values()))
    dl.kv("CHUNK_SIZE / CHUNK_OVERLAP", "400 / 50 characters")
    dl.kv("embedded text length min / mean / max",
          f"{min(embedded)} / {sum(embedded) // len(embedded)} / {max(embedded)}")
    dl.kv("chunks over CHUNK_SIZE", sum(1 for n in embedded if n > 400))
    print()
    dl.para("404 = 391 + 13. The text that gets embedded is \"Question: ... Answer: ...\", so "
            "no chunk crosses a Q&A boundary and the chunker only had to decide what to do "
            "about the 13 pairs whose combined text passed 400 characters.")

    dl.section("B. every chunk can be traced back to its source")
    sample = chunks[0]
    dl.kv("fields on a chunk", ", ".join(sample.keys()))
    for chunk in chunks:
        if per_pair[chunk["qa_id"]] > 1:
            dl.kv("a split pair", f"qa_id={chunk['qa_id']} part_idx={chunk['part_idx']} "
                                  f"line_no={chunk['line_no']}")
            dl.kv("", dl.clip(chunk["text"], 62), 34)
            break
    print()
    dl.para("qa_id says which pair, part_idx says which piece of it, line_no says where in "
            "scam_q_a.txt to look. Without those three a retrieved chunk is a floating string "
            "and a citation cannot be checked. LAB1 needed the same property and could not use "
            "the record id alone for it - see problem03.")

    dl.section("C. what a structure-blind fixed split does to the same data")
    joined = " ".join(f"{entry['question']} {entry['answer']}" for entry in entries)
    naive = fixed_chunks(joined, 400, 50)

    dl.kv("characters in the whole knowledge base", len(joined))
    dl.kv("chunks from a 400/50 character window", len(naive))
    dl.kv("chunks from structure-aware splitting", len(chunks))
    print()
    print("  first three windows of the naive split:")
    for window in naive[:3]:
        dl.bullet(dl.clip(window, 68))
    print()
    dl.para("The counts are close, which is the misleading part - the naive split produces a "
            "similar number of chunks and they are the right size. What it loses is which "
            "question each piece answers. A window that starts mid-answer and ends mid-question "
            "carries two half-topics, so its embedding sits between them and matches neither "
            "query well. Worse, the answer it half-contains may be retrieved for the question "
            "it does not contain.")

    dl.section("D. overlap, and the weakness the split leaves behind")
    tails = [chunk for chunk in chunks if chunk["part_idx"] > 0]
    heads = [chunk for chunk in chunks if chunk["part_idx"] == 0 and per_pair[chunk["qa_id"]] > 1]

    pair_id = tails[0]["qa_id"]
    parts = sorted([c for c in chunks if c["qa_id"] == pair_id], key=lambda c: c["part_idx"])
    for part in parts:
        dl.kv(f"part_idx {part['part_idx']}  ({len(part['text'])} chars)",
              dl.clip(part["text"], 46), 30)

    seam = longest_seam(parts[0]["text"], parts[1]["text"])
    print()
    dl.kv("text repeated across the seam", f"{len(seam)} characters")
    dl.bullet(dl.clip(seam, 66))
    dl.para("That is CHUNK_OVERLAP doing its job: a sentence that straddles the cut appears "
            "whole in at least one of the two chunks.")

    print()
    dl.kv("tail chunks (part_idx > 0)", len(tails))
    dl.kv("their embedded length min / max",
          f"{min(len(c['text']) for c in tails)} / {max(len(c['text']) for c in tails)} characters")
    dl.kv("tails that still carry the question", sum(1 for c in tails if "Question:" in c["text"]))
    head_sizes = sorted({len(chunk["text"]) for chunk in heads})
    dl.kv("head chunks, sizes seen", f"{head_sizes} characters")
    print()
    dl.para("This is the weakness the measurement exposes. split_text() cuts the combined "
            "string by character position, so only the first piece keeps the \"Question: ...\" "
            "prefix. All 13 tail chunks are a bare 54-104 character fragment of an answer with "
            "no indication of what question it answers - the shortest, least contextual "
            "embeddings in the whole index.")
    print()
    dl.para("It is survivable here because `answer` is stored in full on every part, so a tail "
            "chunk that does get retrieved still displays the complete answer and the citation "
            "is still correct. But the embedding that decides whether it is retrieved at all "
            "was computed from the fragment. Repeating the question prefix on each part would "
            "cost 13 short strings and remove the problem; it is the change to make if this "
            "knowledge base grows longer answers.")

    dl.section("E. LAB1: the same decision on a different shape of data")
    try:
        rows = dl.lab1_chunks()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        rows = []

    if rows:
        strategies = collections.Counter(row["strategy"] for row in rows)
        tokens = [row["token_count"] for row in rows]
        dl.kv("chunks", len(rows))
        dl.kv("strategy used", dict(strategies))
        dl.kv("token_count min / mean / max",
              f"{min(tokens)} / {sum(tokens) // len(tokens)} / {max(tokens)}")
        dl.kv("counted with", "tiktoken cl100k_base")
        print()
        dl.para("Job postings are prose with headings, so LAB1 cuts on the headings the cleaning "
                "stage preserved and packs sections up to a token budget. Token counting uses "
                "cl100k_base - the encoding the embedding model actually uses - so a chunk "
                "size of 500 means the same 500 the embedder will measure. Counting characters "
                "or whitespace words here would let a chunk silently exceed the model's input "
                "limit and be truncated, losing the tail of a posting with no error raised.")

    dl.section("Cause")
    dl.para("Chunking is where retrieval quality is decided, before any model is involved. A "
            "chunk is the smallest unit the system can return, so a chunk that mixes two "
            "subjects can never be a precise answer to either, and a chunk that ends mid-thought "
            "cannot be a complete answer to anything.")

    dl.section("Fix applied")
    dl.bullet("LAB2 / LAB3: one Q&A pair is one chunk. Only answers over CHUNK_SIZE are split, "
              "with CHUNK_OVERLAP characters carried across the seam.")
    dl.bullet("LAB3: split pieces keep qa_id, part_idx and line_no, so a chunk always resolves "
              "back to a pair and a line in the source file.")
    dl.bullet("LAB1: strategy is an argument (fixed / paragraph / heading), not a constant, and "
              "heading is the default because the data has headings.")
    dl.bullet("LAB1: token counting uses the embedding model's own encoding rather than a "
              "character or word approximation.")
    dl.bullet("Still open: the 13 tail chunks lose their question prefix (section D). Reported "
              "rather than patched, because changing the splitter means rebuilding the index "
              "and re-running every measurement in LAB3.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/text_splitter.py, LAB1/Pipeline/chunking.py")


if __name__ == "__main__":
    run()
