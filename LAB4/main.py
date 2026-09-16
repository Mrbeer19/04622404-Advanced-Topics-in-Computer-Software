# -*- coding: utf-8 -*-
"""LAB4 - DL-05 RAG System Development II

Ten problems found while building LAB1, LAB2 and LAB3, each one reproduced
against the artefacts those labs actually produced.

Run:
    python main.py            # menu
    python main.py 7          # one problem
    python main.py 0          # all ten, in order
    python main.py 0 > report.txt

Every module is importable on its own and runs with the standard library only.
The measured numbers are read from the committed LAB1/LAB3 outputs rather than
recomputed, so nothing here needs an LLM, a GPU or a model download.
"""

import sys

from problem01_hallucination import run as problem01
from problem02_transformer import run as problem02
from problem03_data_quality import run as problem03
from problem04_chunking import run as problem04
from problem05_metadata import run as problem05
from problem06_reranking import run as problem06
from problem07_generation import run as problem07
from problem08_config import run as problem08
from problem09_evaluation import run as problem09
from problem10_reproducibility import run as problem10

PROBLEMS = {
    1: ("Hallucination and the silent fallback", "LAB3", problem01),
    2: ("Vocabulary mismatch / token position", "LAB2, LAB3", problem02),
    3: ("Data quality: skips, ids, duplicates", "LAB1, LAB4", problem03),
    4: ("Chunk size, overlap, traceability", "LAB1, LAB2, LAB3", problem04),
    5: ("Metadata filtering and index drift", "LAB3", problem05),
    6: ("Top-k and re-ranking", "LAB3", problem06),
    7: ("Retrieval correct, generation wrong", "LAB3", problem07),
    8: ("Configuration: switches that do nothing", "LAB3", problem08),
    9: ("Evaluating the evaluation", "LAB3", problem09),
    10: ("Reproducibility with an LLM in the loop", "LAB3", problem10),
}

WIDTH = 78


def show_menu():
    print()
    print("*" * WIDTH)
    print("  LAB4 - DL-05 RAG System Development II")
    print("  Problems found across LAB1-LAB3, and how each one was fixed")
    print("*" * WIDTH)
    print("   0. Run all")
    for number, (name, origin, _) in PROBLEMS.items():
        print(f"  {number:2}. {name:<44} [{origin}]")
    print("*" * WIDTH)


def execute(number):
    if number == 0:
        for index in sorted(PROBLEMS):
            PROBLEMS[index][2]()
        return True

    if number not in PROBLEMS:
        print(f"Please choose a number between 0 and {max(PROBLEMS)}")
        return False

    PROBLEMS[number][2]()
    return True


def main_loop():
    while True:
        show_menu()
        choice = input(f"Select a problem [0-{max(PROBLEMS)}] or Q to quit: ").strip()

        if choice.upper() == "Q":
            print("Exiting.")
            return

        try:
            execute(int(choice))
        except ValueError:
            print(f"Please enter a number between 0 and {max(PROBLEMS)}, or Q.")
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        argument = sys.argv[1].strip()
        if argument.upper() == "Q":
            sys.exit(0)
        try:
            sys.exit(0 if execute(int(argument)) else 1)
        except ValueError:
            print(f"Please enter a number between 0 and {max(PROBLEMS)}, or Q.")
            sys.exit(1)
    else:
        main_loop()
