# -*- coding: utf-8 -*-
"""Shared loader for LAB4.

Every problem module in this folder reads the *same* real artefacts that LAB1-LAB3
produced, instead of inventing sample data. This module is the only place that
knows where those artefacts live.

Two things it does that the course template does not:

1. `load_qa()` counts what it throws away. The template silently skips any block
   it cannot parse, so a knowledge base that half-loads looks exactly like one
   that loads cleanly. `load_qa_report()` returns the skip reasons, and
   `problem03` prints them.
2. It resolves the LAB1/LAB3 artefacts by path rather than copying them here, so
   there is one copy of the knowledge base in the repository and the numbers in
   this folder can never drift away from the lab that produced them.
"""

import json
import os
import re
import sys
import textwrap

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)

LAB1_OUTPUTS = os.path.join(REPO_DIR, "LAB1", "Pipeline", "outputs")
LAB3_PROJECT = os.path.join(REPO_DIR, "LAB3", "RAG-Project")

DATA_PATH = os.path.join(LAB3_PROJECT, "data", "scam_q_a.txt")
GOLDEN_SET_PATH = os.path.join(LAB3_PROJECT, "data", "golden_set.json")
CHUNKS_PATH = os.path.join(LAB3_PROJECT, "outputs", "chunks.json")
EVAL_RETRIEVAL_PATH = os.path.join(LAB3_PROJECT, "outputs", "eval_retrieval.json")
EVAL_TRANSFORM_PATH = os.path.join(LAB3_PROJECT, "outputs", "eval_query_transform.json")
EVAL_GENERATION_PATH = os.path.join(LAB3_PROJECT, "outputs", "eval_generation.json")
INDEX_META_PATH = os.path.join(LAB3_PROJECT, "vector_db", "index_meta.json")
CONFIG_PATH = os.path.join(LAB3_PROJECT, "config.py")
LAB3_SRC = os.path.join(LAB3_PROJECT, "src")

_HEADER_RE = re.compile(r"\[หมวด:\s*(.+?)\]")

DEFAULT_LANG = "ทางการ"


# ----------------------------------------------------------------- knowledge base

def load_qa_report(path=DATA_PATH):
    """Parse the knowledge base and report what was skipped.

    Returns (entries, stats). `stats["skipped"]` maps a reason to a count, so a
    silent parse loss shows up as a number instead of as missing answers later.
    """
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()

    entries = []
    stats = {"blocks": 0, "skipped": {}}

    def skip(reason):
        stats["skipped"][reason] = stats["skipped"].get(reason, 0) + 1

    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        stats["blocks"] += 1

        if block.startswith("#"):
            skip("file header / comment")
            continue

        lines = block.split("\n")
        if len(lines) < 3:
            skip("fewer than 3 lines")
            continue

        header, q_line, a_line = lines[0], lines[1], lines[2]

        match = _HEADER_RE.match(header)
        if not match:
            skip("no [หมวด: ...] header")
            continue

        raw_category = match.group(1).strip()
        if "|" in raw_category:
            category, lang = [part.strip() for part in raw_category.split("|", 1)]
            lang = lang.replace("ภาษา:", "").strip()
        else:
            category, lang = raw_category, DEFAULT_LANG

        question = q_line[2:].strip() if q_line.startswith("Q:") else q_line.strip()
        answer = a_line[2:].strip() if a_line.startswith("A:") else a_line.strip()
        if not question or not answer:
            skip("empty question or answer")
            continue

        entries.append({
            "id": len(entries),
            "category": category,
            "lang": lang,
            "question": question,
            "answer": answer,
            "text": f"{question} {answer}",
        })

    stats["parsed"] = len(entries)
    return entries, stats


def load_qa(path=DATA_PATH):
    """The entry list on its own, for modules that do not need the stats."""
    entries, _ = load_qa_report(path)
    return entries


def categories(entries=None):
    entries = entries if entries is not None else load_qa()
    return sorted({entry["category"] for entry in entries})


def languages(entries=None):
    entries = entries if entries is not None else load_qa()
    return sorted({entry["lang"] for entry in entries})


# ------------------------------------------------------------- measured artefacts

class MissingArtefact(Exception):
    """Raised when a LAB1/LAB3 output this module needs is not on disk."""


def _load_json(path, produced_by):
    if not os.path.exists(path):
        raise MissingArtefact(
            f"{os.path.relpath(path, REPO_DIR)} is missing - produced by {produced_by}"
        )
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def chunks():
    """LAB3 chunks.json - 404 chunks with qa_id / part_idx / line_no."""
    return _load_json(CHUNKS_PATH, "LAB3 build_index.py")


def golden_set():
    """LAB3 golden_set.json - the evaluation items and their query variants."""
    return _load_json(GOLDEN_SET_PATH, "LAB3 evaluation/build_golden_set.py")


def eval_retrieval():
    """LAB3 eval_retrieval.json - scores per retrieval configuration."""
    return _load_json(EVAL_RETRIEVAL_PATH, "LAB3 evaluation/eval_retrieval.py")


def eval_query_transform():
    """LAB3 eval_query_transform.json - scores and every query actually searched."""
    return _load_json(EVAL_TRANSFORM_PATH, "LAB3 evaluation/eval_query_transform.py")


def eval_generation():
    """LAB3 eval_generation.json - answer quality per question."""
    return _load_json(EVAL_GENERATION_PATH, "LAB3 evaluation/eval_generation.py")


def index_meta():
    """LAB3 index_meta.json - the fingerprint the FAISS index was built from."""
    return _load_json(INDEX_META_PATH, "LAB3 build_index.py")


def lab1_chunks():
    """Every chunk LAB1 stage 3 produced, from all four source files."""
    if not os.path.isdir(LAB1_OUTPUTS):
        raise MissingArtefact("LAB1/Pipeline/outputs is missing")
    rows = []
    for name in sorted(os.listdir(LAB1_OUTPUTS)):
        if name.startswith("chunked_") and name.endswith(".json"):
            with open(os.path.join(LAB1_OUTPUTS, name), encoding="utf-8") as handle:
                rows.extend(json.load(handle))
    if not rows:
        raise MissingArtefact("no chunked_*.json in LAB1/Pipeline/outputs")
    return rows


def lab1_boilerplate():
    """The boilerplate lines LAB1 stage 2 found and stripped."""
    return _load_json(os.path.join(LAB1_OUTPUTS, "boilerplate_lines.json"),
                      "LAB1 Pipeline/02_data_cleaning.py")


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# ------------------------------------------------------------------- report layout

WIDTH = 78


def title(text):
    print()
    print("=" * WIDTH)
    print(text)
    print("=" * WIDTH)


def section(label, text=""):
    print()
    print(f"-- {label} " + "-" * max(0, WIDTH - len(label) - 4))
    if text:
        print(text)


def bullet(text, indent=0):
    """Print one bullet, wrapped to the report width with a hanging indent."""
    lead = " " * indent + "  - "
    print(textwrap.fill(" ".join(str(text).split()), width=WIDTH, break_long_words=False,
                        initial_indent=lead, subsequent_indent=" " * len(lead)))


def para(text):
    """Print prose wrapped to the report width, without a bullet marker."""
    print(textwrap.fill(" ".join(text.split()), width=WIDTH, break_long_words=False,
                        initial_indent="  ", subsequent_indent="  "))


def kv(key, value, width=34):
    print(f"  {key:<{width}} {value}")


def table(headers, rows, align_right=()):
    """Print a plain fixed-width table. `align_right` holds column indexes."""
    cells = [[str(cell) for cell in row] for row in rows]
    widths = []
    for i, head in enumerate(headers):
        longest = max([len(row[i]) for row in cells], default=0)
        widths.append(max(len(str(head)), longest))

    def line(values):
        parts = []
        for i, value in enumerate(values):
            text = str(value)
            parts.append(text.rjust(widths[i]) if i in align_right else text.ljust(widths[i]))
        print("  " + "  ".join(parts).rstrip())

    line(headers)
    print("  " + "  ".join("-" * width for width in widths))
    for row in cells:
        line(row)


def clip(text, length=90):
    text = " ".join(str(text).split())
    return text if len(text) <= length else text[:length - 1] + "..."


if __name__ == "__main__":
    data, stats = load_qa_report()
    print("Knowledge base:", os.path.relpath(DATA_PATH, REPO_DIR))
    print("Blocks in file:", stats["blocks"])
    print("Q&A parsed    :", stats["parsed"])
    print("Skipped       :", stats["skipped"] or "none")
    print("Categories    :", len(categories(data)))
    print("Registers     :", ", ".join(languages(data)))
    print("First entry   :", clip(data[0]["question"]))
