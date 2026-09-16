# -*- coding: utf-8 -*-
"""Problem 03 - Data quality: duplicates, noise, and identifiers that cannot be joined.

Where it came from
    LAB1 (DL-02), the team data pipeline - stages 2 and 3.
    LAB4 itself, while writing data_loader.py.

The course template simulates noise by taking two real questions and adding
underscores and exclamation marks to them. That shows what normalisation is for,
but nothing in it can fail, because the noise was manufactured two lines earlier.

This module reports three data-quality problems that were actually hit:

  1. **A parser that throws work away without saying so.** The template's
     `load_qa()` calls `continue` on every block it cannot parse. If the file
     format drifts, the knowledge base silently gets smaller and retrieval just
     starts missing answers. `data_loader.load_qa_report()` counts the skips.
  2. **Identifiers that are not comparable across sources.** LAB1 merged four
     scraped files into one corpus. Jobicy identifies a posting with an int,
     AIDevBoard with a UUID string, and the two id spaces are unrelated - so an
     id on its own cannot resolve a chunk back to the posting it came from.
  3. **Boilerplate that survives cleaning and then gets embedded.** 77 lines of
     legal and template text repeated across postings. Left in, every chunk
     containing them looks a little bit like every other chunk.
"""

import collections
import difflib
import re

import data_loader as dl


def normalize(text):
    text = text.lower()
    text = re.sub(r"[_@!\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def count_duplicates(entries, field):
    counts = collections.Counter(normalize(entry[field]) for entry in entries)
    return sum(1 for count in counts.values() if count > 1)


def similarity(left, right):
    return difflib.SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def near_duplicate_pairs(entries, threshold=0.95):
    """Pairs whose question *and* answer are both at least `threshold` alike.

    An exact-match check misses a variant that was copied and then lightly
    edited, which is exactly the mistake this knowledge base contains. Comparing
    every pair is O(n^2); at 391 entries that is 76k comparisons and runs in
    well under a second, so there is no reason to approximate.
    """
    found = []
    for i, left in enumerate(entries):
        for right in entries[i + 1:]:
            q_ratio = similarity(left["question"], right["question"])
            if q_ratio < threshold:
                continue
            a_ratio = similarity(left["answer"], right["answer"])
            if a_ratio >= threshold:
                found.append((left, right, q_ratio, a_ratio))
    return found


def difference(left, right):
    """The edits that turn `left` into `right`, as (tag, removed, added)."""
    matcher = difflib.SequenceMatcher(None, left, right)
    edits = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            edits.append((tag, left[i1:i2], right[j1:j2]))
    return edits


def run():
    dl.title("PROBLEM 03  Data quality")

    # ------------------------------------------------------------------ 1
    dl.section("A. a parser that skips blocks silently is a data-loss bug")
    entries, stats = dl.load_qa_report()
    dl.kv("blocks separated by a blank line", stats["blocks"])
    dl.kv("Q&A pairs parsed", stats["parsed"])
    for reason, count in sorted(stats["skipped"].items()):
        dl.kv(f"skipped - {reason}", count)
    dl.kv("accounted for", stats["parsed"] + sum(stats["skipped"].values()) == stats["blocks"])
    dl.para("Here every skipped block is a file header comment, so nothing was lost. The point "
            "is that the number is now on screen. The course template returns only the entry "
            "list, so a knowledge base that half-parsed and one that parsed cleanly look "
            "identical from the outside, and the symptom surfaces much later as retrieval "
            "quietly missing answers that are in the file.")

    # ------------------------------------------------------------------ 2
    dl.section("B. LAB1: four sources, two incompatible kinds of identifier")
    try:
        rows = dl.lab1_chunks()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        rows = []

    if rows:
        by_source = collections.Counter(row["source"] for row in rows)
        id_types = collections.Counter(type(row["id"]).__name__ for row in rows)
        dl.table(["source file", "chunks", "id type"],
                 [[source, count,
                   sorted({type(r["id"]).__name__ for r in rows if r["source"] == source})[0]]
                  for source, count in by_source.most_common()],
                 align_right={1})
        print()
        dl.kv("chunks in the merged corpus", len(rows))
        dl.kv("postings they came from", len({(r["source"], str(r["id"])) for r in rows}))
        dl.kv("id types present", dict(id_types))
        dl.kv("unique on chunk_index alone",
              f"{len({r['chunk_index'] for r in rows})}  <- collides immediately")
        dl.kv("unique on id alone", len({str(r["id"]) for r in rows}))
        dl.kv("unique on chunk_id (source:id:index)", len({r["chunk_id"] for r in rows}))
        print()
        dl.para("The four snapshots happen not to collide today, which is exactly what makes "
                "this dangerous: a join on `id` alone passes every test until Jobicy issues an "
                "id that matches an AIDevBoard UUID, or a fifth source is added. The id spaces "
                "were never coordinated, so the pair (source, id) is the only thing that is "
                "actually a key - and `5` and `\"5\"` do not even compare equal in Python.")

    # ------------------------------------------------------------------ 3
    dl.section("C. LAB1: boilerplate that survives into the embeddings")
    try:
        boilerplate = dl.lab1_boilerplate()
        dl.kv("repeated lines detected and stripped", len(boilerplate))
        for line in boilerplate[:6]:
            dl.bullet(dl.clip(line, 66))
        dl.para("These lines appear in many postings at once. Left in, every chunk that carries "
                "them shares vocabulary with every other such chunk, so their embeddings drift "
                "toward each other and a query about any of them retrieves an arbitrary one.")
    except dl.MissingArtefact as error:
        print(f"  {error}")

    # ------------------------------------------------------------------ 4
    dl.section("D. the real knowledge base, checked for near-duplicates")
    dl.kv("Q&A pairs", len(entries))
    dl.kv("exact duplicate questions", count_duplicates(entries, "question"))
    dl.kv("exact duplicate answers", count_duplicates(entries, "answer"))

    near = near_duplicate_pairs(entries, threshold=0.95)
    dl.kv(f"pairs at least 95 % identical on both fields", len(near))

    for left, right, q_ratio, a_ratio in near:
        print()
        dl.kv(f"id {left['id']} [{left['lang']}]", dl.clip(left["question"], 50), 22)
        dl.kv(f"id {right['id']} [{right['lang']}]", dl.clip(right["question"], 50), 22)
        dl.kv("question similarity", f"{q_ratio:.3f}", 22)
        dl.kv("answer similarity", f"{a_ratio:.3f}", 22)
        for tag, old, new in difference(left["answer"], right["answer"])[:3]:
            dl.kv(f"answer {tag}", f"{old!r} -> {new!r}", 22)

    registers = collections.Counter(
        tuple(sorted((left["lang"], right["lang"]))) for left, right, _, _ in near)

    print()
    dl.para(f"{len(near)} real defects in the knowledge base, found by running the check rather "
            "than assuming the data was clean. Every one of them is the same mistake, and the "
            "register pairing gives it away:")
    print()
    for pair, count in registers.most_common():
        dl.bullet(f"{count} pair(s)  {pair[0]} <-> {pair[1]}")
    print()
    dl.para("A slang variant that was copied from the conversational one and then edited by a "
            "word or two, instead of being rewritten. None of these is a slang variant in any "
            "useful sense, so the slang register is smaller than its count of 102 claims - and "
            "when one of these subjects is retrieved, two of the three top-k slots come back "
            "carrying the same fact.")
    print()
    dl.para("This also matters for problem02 and problem09. The whole argument for this "
            "knowledge base is that the three registers say the same things in different "
            "words, and the slang variant is where dense retrieval is supposed to struggle. "
            "A slang query that is 97 % identical to its conversational twin does not test "
            "that at all - it is the golden-set leakage of problem09, reproduced inside the "
            "data itself.")
    print()
    dl.para("Note that an exact-match duplicate check finds one of these five. The other four "
            "differ by a word and pass it. Near-duplicate detection is what the data needed.")
    print()
    dl.para("They are reported here and left in the file on purpose. Editing scam_q_a.txt "
            "invalidates the committed FAISS and BM25 indexes built from it, which is the "
            "situation problem05 is about - the fix is to rewrite these slang variants and "
            "re-run build_index.py as one change, not to patch the text and leave the index "
            "behind.")

    dl.section("Cause")
    dl.para("Data problems are cheap to fix at the stage that creates them and expensive "
            "everywhere downstream. A dropped block, an ambiguous id and a boilerplate line all "
            "look like retrieval bugs by the time anyone notices them, because the retriever is "
            "the first stage that produces a visibly wrong answer.")

    dl.section("Fix applied")
    dl.bullet("LAB1 chunking.py writes chunk_id = f\"{source}:{id}:{index}\" and keeps `id`, "
              "`source` and `source_file` on every chunk, so a chunk always resolves back to "
              "one posting in one file.")
    dl.bullet("LAB1 chunk_record() raises KeyError on a record with no `id` instead of "
              "inventing one - a chunk that cannot be traced is worse than a missing chunk.")
    dl.bullet("LAB1 stage 2 collects repeated lines into boilerplate_lines.json and strips "
              "them before chunking, so the removal is auditable rather than implicit.")
    dl.bullet("LAB4 data_loader.load_qa_report() returns the skip counts, and this module "
              "prints them.")
    print()
    dl.para("Source: LAB1/Pipeline/chunking.py, LAB1/Pipeline/cleaning.py, "
            "LAB4/data_loader.py")


if __name__ == "__main__":
    run()
