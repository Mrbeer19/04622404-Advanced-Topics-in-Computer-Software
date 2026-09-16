# -*- coding: utf-8 -*-
"""Problem 05 - Metadata: filtering on it, and the metadata about the index itself.

Where it came from
    LAB3 (DL-04), `src/index_meta.py` and the register fields in the knowledge base.

The course template makes one point: similarity search returns the document with
the most matching words, and that document may carry the wrong metadata - the
right content in the wrong register for the system asking. That is real, and part
A reproduces it on the scam knowledge base, which is written in three registers.

Part B is the metadata problem that actually cost time in LAB3, and it is not
about the documents at all. It is about the index.

The FAISS index and the BM25 index are built from scam_q_a.txt by build_index.py
and then committed. Nothing in the retrieval path re-reads the source file. So if
the knowledge base is edited, or CHUNK_SIZE changes, or the embedding model is
swapped, retrieval keeps answering - from the old data - and every result is
quietly wrong with no error anywhere. This happened while retargeting the project
from the LAB2 finance knowledge base to the scam one.

The fix is index_meta.py: fingerprint the dataset and the settings that determine
the index, store that next to the index, and compare on every startup.
"""

import os

import data_loader as dl

QUERY = "บัญชีม้า คือ อะไร โดน คดี"


def score(query, text):
    """Keyword overlap - the same weak scorer the template uses, on purpose."""
    return sum(word in text for word in query.split())


def search(entries, query, lang=None, top_k=5):
    pool = entries if lang is None else [e for e in entries if e["lang"] == lang]
    ranked = sorted(pool,
                    key=lambda entry: score(query, entry["question"] + " " + entry["answer"]),
                    reverse=True)
    return ranked[:top_k]


TRACKED_SETTINGS = ["CHUNK_SIZE", "CHUNK_OVERLAP", "EMBEDDING_MODEL_NAME"]


def current_state():
    """Recompute the fingerprint the way LAB3 index_meta.get_current_state() does."""
    stat = os.stat(dl.DATA_PATH)
    return {"size": stat.st_size, "mtime": int(stat.st_mtime)}


def run():
    entries = dl.load_qa()

    dl.title("PROBLEM 05  Metadata filtering, and metadata about the index")

    dl.section("A. right content, wrong register")
    dl.para(f"query, asked by a help desk that must answer in formal register:  {QUERY}")

    print()
    print("  top 5, no metadata filter:")
    dl.table(["rank", "register", "question"],
             [[rank, entry["lang"], dl.clip(entry["question"], 48)]
              for rank, entry in enumerate(search(entries, QUERY), 1)],
             align_right={0})

    print()
    print("  top 5, filtered to lang = ทางการ:")
    dl.table(["rank", "register", "question"],
             [[rank, entry["lang"], dl.clip(entry["question"], 48)]
              for rank, entry in enumerate(search(entries, QUERY, lang="ทางการ"), 1)],
             align_right={0})

    print()
    dl.para("Unfiltered, the top two documents are written in conversational and slang "
            "register - and they are a near-duplicate pair, the same problem03 defect showing "
            "up in a ranking. The one document that actually defines บัญชีม้า and states the "
            "offence sits at rank 4. Filtering on the register moves it to rank 2 and clears "
            "both unusable documents out of the top-k entirely.")
    print()
    dl.para("Note what the filter does not do: it does not make the scorer better. Rank 1 is "
            "still a weak match. Metadata filtering removes documents the system cannot use, "
            "which is a different job from ranking the ones it can - that is problem06.")
    print()
    dl.para("Similarity picks the document with the most matching words. It has no opinion "
            "about whether that document is written in the register the caller needs. A bank's "
            "help desk cannot answer a customer in slang however relevant the content is, so "
            "the register has to be a filter on the candidate set, not something the scorer is "
            "hoped to get right.")
    print()
    dl.para("This is only possible because the register was recorded as metadata when the file "
            "was parsed. It lives on the [หมวด: ... | ภาษา: ...] header line, data_loader keeps "
            "it as `lang`, and the chunks keep `category`. Metadata that is not carried through "
            "chunking cannot be filtered on later, however obvious it looked in the source file.")

    dl.section("B. the index carries metadata too, and it can go stale")
    try:
        saved = dl.index_meta()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    now = current_state()

    dl.kv("index built from", saved.get("source_file"))
    dl.kv("chunks in the index", saved.get("n_chunks"))
    print()
    dl.table(["tracked value", "when the index was built", "now"],
             [["file size", saved["file"]["size"], now["size"]],
              ["file mtime", saved["file"]["mtime"], now["mtime"]]] +
             [[name, saved["settings"].get(name), saved["settings"].get(name)]
              for name in TRACKED_SETTINGS])

    problems = []
    if saved["file"] != now:
        problems.append("scam_q_a.txt has changed since the index was built")

    print()
    if problems:
        for problem in problems:
            dl.bullet(problem)
        dl.para("main.py prints this warning at startup and the results that follow come from "
                "the old data.")
    else:
        dl.kv("verdict", "index matches the dataset it was built from")

    dl.section("C. what it looks like when the fingerprint is not checked")
    stale = dict(saved["file"])
    stale["size"] = stale["size"] - 1
    dl.kv("simulated: one character removed from the KB", "")
    dl.kv("saved fingerprint", stale, 22)
    dl.kv("current fingerprint", now, 22)
    dl.kv("find_problems() would report",
          "scam_q_a.txt was modified after the index was created", 22)
    print()
    dl.para("Without this check the system answers normally. Retrieval runs against the old "
            "FAISS vectors and the old BM25 index, the citations point at line numbers in a "
            "file that no longer says that, and nothing raises. This is the failure mode that "
            "made problem03 leave its five knowledge-base defects unpatched: editing the text "
            "without rebuilding the index is worse than the defect it fixes.")

    dl.section("Cause")
    dl.para("Metadata is the part of the data that is not the text, and both halves of this "
            "problem come from the same mistake - assuming that because something is obvious "
            "in the source it will still be knowable downstream. The register is obvious in "
            "scam_q_a.txt and invisible in a FAISS vector. Which file an index was built from "
            "is obvious while you are building it and invisible the next time you start up.")

    dl.section("Fix applied in LAB3")
    dl.bullet("Register and category are parsed from the header line and carried onto every "
              "chunk, so retrieval can filter on them.")
    dl.bullet("index_meta.py records the source file's size and mtime plus CHUNK_SIZE, "
              "CHUNK_OVERLAP and EMBEDDING_MODEL_NAME into vector_db/index_meta.json.")
    dl.bullet("warn_if_stale() compares that fingerprint against the current state and main.py "
              "calls it on startup, so a stale index announces itself instead of answering.")
    dl.bullet("TRACKED_SETTINGS is a list, so adding a setting that invalidates the index is "
              "one line rather than a new comparison.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/index_meta.py, LAB3/RAG-Project/main.py")


if __name__ == "__main__":
    run()
