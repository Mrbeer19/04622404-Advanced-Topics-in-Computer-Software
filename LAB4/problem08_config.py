# -*- coding: utf-8 -*-
"""Problem 08 - Configuration: a switch that does nothing is worse than no switch.

Where it came from
    LAB3 (DL-04), `config.py` and `main.py`.

The course template prints a hard-coded CONFIG dictionary and then prints which
branch each flag would take. Every flag in it is honoured, because the same
function that reads the flag also prints the consequence.

The real defect in LAB3 was a flag that was read and then had nothing to do.
SHOW_SOURCES existed in config.py, it was documented, and the block in main.py
that printed the source list was commented out - along with the
`rag.show_settings()` call. Setting SHOW_SOURCES = True changed nothing on
screen, which reads as "sources are not working" rather than "this switch is not
wired up".

So this module does not print a config. It reads the real config.py, finds every
switch in it, and greps the rest of the project for code that consumes each one.
A switch with no consumer is reported. That check would have caught the defect
in one run.
"""

import os
import re

import data_loader as dl

SWITCH_RE = re.compile(r"^(?P<name>(?:USE_|SHOW_)[A-Z_]+)\s*=\s*(?P<value>True|False)",
                       re.MULTILINE)

# Files that only declare or document a switch do not count as consumers of it.
DECLARING_FILES = {"config.py"}


def read_switches(path):
    """Every boolean USE_* / SHOW_* switch declared in config.py, in file order."""
    text = dl.read_text(path)
    return [(match.group("name"), match.group("value") == "True")
            for match in SWITCH_RE.finditer(text)]


def project_files(root):
    """Every .py file in the LAB3 project, excluding the virtualenv and caches."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".venv", "venv", "__pycache__", ".git"}]
        for name in sorted(filenames):
            if name.endswith(".py"):
                found.append(os.path.join(dirpath, name))
    return found


def find_consumers(switch, files, root):
    """Files that read `switch` in live code, with the commented-out uses counted."""
    live, commented = [], []
    pattern = re.compile(rf"\bconfig\.{switch}\b|\b{switch}\b")
    for path in files:
        relative = os.path.relpath(path, root).replace("\\", "/")
        if os.path.basename(path) in DECLARING_FILES:
            continue
        hits = live_hits = dead_hits = 0
        for line in dl.read_text(path).splitlines():
            if not pattern.search(line):
                continue
            hits += 1
            if line.lstrip().startswith("#"):
                dead_hits += 1
            else:
                live_hits += 1
        if live_hits:
            live.append((relative, live_hits))
        if dead_hits:
            commented.append((relative, dead_hits))
    return live, commented


def run():
    dl.title("PROBLEM 08  RAG configuration")

    dl.section("A. the switches the project actually declares")
    try:
        switches = read_switches(dl.CONFIG_PATH)
    except OSError as error:
        print(f"  {error}")
        return

    files = project_files(dl.LAB3_PROJECT)
    dl.kv("config file", os.path.relpath(dl.CONFIG_PATH, dl.REPO_DIR))
    dl.kv("switches found", len(switches))
    dl.kv("python files searched", len(files))

    dl.section("B. is every switch wired to something?")
    rows = []
    unwired = []
    for name, default in switches:
        live, commented = find_consumers(name, files, dl.LAB3_PROJECT)
        if live:
            verdict = "wired"
        elif commented:
            verdict = "only in comments"
            unwired.append(name)
        else:
            verdict = "NO CONSUMER"
            unwired.append(name)
        rows.append([name, str(default), len(live), len(commented), verdict])

    dl.table(["switch", "default", "live uses", "commented", "verdict"], rows,
             align_right={2, 3})

    print()
    if unwired:
        for name in unwired:
            dl.bullet(f"{name} is declared but nothing live reads it")
    else:
        dl.para("Every switch in config.py has live code reading it. This is the state after "
                "the LAB3 fix; before it, SHOW_SOURCES would have appeared in this table with "
                "its only occurrence inside a comment in main.py.")

    dl.section("C. where each switch is read")
    for name, _ in switches:
        live, commented = find_consumers(name, files, dl.LAB3_PROJECT)
        print(f"  {name}")
        for path, count in live:
            dl.bullet(f"{path}  x{count}", indent=2)
        if not live:
            dl.bullet("nothing", indent=2)

    dl.section("D. the pipeline those switches describe")
    defaults = dict(switches)
    stages = [
        ("USE_MEMORY", "conversation history is prepended to the prompt",
         "each question is answered on its own"),
        ("USE_QUERY_TRANSFORM", "the query is rewritten or expanded by the LLM first",
         "the query goes to the retriever as typed (after SLANG_MAP normalisation)"),
        ("USE_HYBRID", "BM25 runs alongside dense retrieval, merged with RRF",
         "dense retrieval only"),
        ("USE_RERANK", "a cross-encoder reorders CANDIDATE_K down to TOP_K",
         "the first-stage ranking is final"),
        ("USE_LLM", "the LLM writes an answer from the retrieved context",
         "the retrieved text is returned as-is"),
        ("SHOW_SOURCES", "the [n] source list is printed under the answer",
         "the answer is printed alone"),
    ]
    for name, when_on, when_off in stages:
        state = defaults.get(name)
        if state is None:
            continue
        dl.kv(f"{name} = {state}", when_on if state else when_off, 30)

    dl.section("Cause")
    dl.para("A configuration file is a promise that each name in it controls something. The "
            "promise is checked by nothing - Python will happily import a module-level constant "
            "that no other line reads. So a switch can be added, documented and then quietly "
            "orphaned by a refactor or a commented-out block, and the only symptom is a feature "
            "that appears not to work.")

    dl.section("Fix applied in LAB3")
    dl.bullet("The commented-out source-list block and the rag.show_settings() call in main.py "
              "were restored, so SHOW_SOURCES and SHOW_DEBUG do what they claim.")
    dl.bullet("Every switch has a measurement behind it in evaluation/, so 'what does this flag "
              "do' has a number rather than a comment as its answer.")
    dl.bullet("This module's grep is the cheap version of that check and runs without an LLM.")
    print()
    dl.para("Source: LAB3/RAG-Project/config.py, LAB3/RAG-Project/main.py")


if __name__ == "__main__":
    run()
