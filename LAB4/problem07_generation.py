# -*- coding: utf-8 -*-
"""Problem 07 - Retrieval was right and the answer was still wrong.

Where it came from
    LAB3 (DL-04), `src/generator.py`, `src/prompt_templates.py`,
    `evaluation/eval_generation.py`.

The course template simulates an unfaithful generator with `context.replace("72
ชั่วโมง", "7 วัน")` - the failure is written by hand, so it always happens and
always in the same place.

Three generation failures were measured for real in LAB3. All three had the
correct chunk in the prompt:

  1. **The no-LLM path answered nothing, ever.** `NoLLM` recovered the context
     by splitting the prompt on the English markers "reference data :" and "Q of
     user", but USER_PROMPT is written in Thai. Neither marker was ever found,
     so the parser fell through and USE_LLM = False replied
     "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง" to every question - a 100 % refusal rate
     that eval_generation reported as a model behaviour.
  2. **The real model refuses too, at 10 %.** With USE_LLM = True and the correct
     chunk in the context window, llama3.1:8b still answered "I could not find
     relevant information" on 2 of 20 questions.
  3. **Faithfulness is measured, correctness is not.** 0.8216 faithfulness is a
     real signal. The 0.6152 "correctness" beside it is word overlap with a
     reference answer, which is not the same thing - see problem09.
"""

import data_loader as dl

# The markers the course code split on, and the ones LAB3 replaced them with.
OLD_CONTEXT_MARKER = "reference data :"
OLD_QUESTION_MARKER = "Q of user"
CONTEXT_HEADER = "ข้อมูลอ้างอิง:"
QUESTION_HEADER = "คำถามของผู้ใช้:"

NO_CONTEXT_MESSAGE = "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"


def build_prompt(context, question):
    """The shape of LAB3's USER_PROMPT, which is written in Thai."""
    return (f"{CONTEXT_HEADER}\n{context}\n\n"
            f"{QUESTION_HEADER} {question}\n\n"
            "ตอบโดยใช้ข้อมูลอ้างอิงข้างต้นเท่านั้น พร้อมอ้างอิงหมายเลข [n]")


def no_llm_broken(prompt):
    """The shipped NoLLM: split on English markers that are not in the prompt."""
    parts = prompt.split(OLD_CONTEXT_MARKER)
    if len(parts) < 2:
        return NO_CONTEXT_MESSAGE
    return parts[1].split(OLD_QUESTION_MARKER)[0].strip()


def no_llm_fixed(prompt):
    """The LAB3 NoLLM: split on the same constants the prompt was built from."""
    parts = prompt.split(CONTEXT_HEADER)
    if len(parts) < 2:
        return NO_CONTEXT_MESSAGE
    return parts[1].split(QUESTION_HEADER)[0].strip()


def run():
    entries = dl.load_qa()

    dl.title("PROBLEM 07  Retrieval correct, generation wrong")

    dl.section("A. the prompt is Thai, the parser looked for English")
    entry = next(e for e in entries if "OTP" in e["question"])
    prompt = build_prompt(f"[1] {entry['answer']}", entry["question"])

    dl.kv("question", dl.clip(entry["question"], 46))
    print()
    dl.kv("markers the shipped parser looked for",
          f"{OLD_CONTEXT_MARKER!r}, {OLD_QUESTION_MARKER!r}")
    dl.kv("present in the prompt?",
          OLD_CONTEXT_MARKER in prompt or OLD_QUESTION_MARKER in prompt)
    dl.kv("markers the prompt is actually built from",
          f"{CONTEXT_HEADER!r}, {QUESTION_HEADER!r}")
    dl.kv("present in the prompt?", CONTEXT_HEADER in prompt and QUESTION_HEADER in prompt)
    print()
    dl.kv("USE_LLM = False, shipped parser", dl.clip(no_llm_broken(prompt), 44))
    dl.kv("USE_LLM = False, LAB3 parser", dl.clip(no_llm_fixed(prompt), 44))
    print()
    dl.para("Every question took the first branch, so the answer was always the "
            "not-found message. Running eval_generation against it produced a 100 % refusal "
            "rate, which reads exactly like a model that will not answer - and no model was "
            "involved at all. The measurement was of a string-splitting bug.")

    dl.section("B. why the fix is a shared constant rather than a corrected string")
    dl.para("Translating the two markers would have worked until the next time the prompt "
            "wording changed. The prompt and the parser are two copies of the same fact - "
            "where the context starts and where the question starts - and the defect was that "
            "they could drift apart silently.")
    print()
    dl.bullet("prompt_templates.py declares CONTEXT_HEADER and QUESTION_HEADER.")
    dl.bullet("USER_PROMPT is built from them.")
    dl.bullet("generator.NoLLM imports the same two names and splits on them.")
    dl.bullet("Editing the header text now moves both sides at once.")

    dl.section("C. the real model, with the right chunk in front of it")
    try:
        generation = dl.eval_generation()
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    summary = generation["summary"]
    results = generation["results"]
    for key, value in summary.items():
        dl.kv(key, value)

    refused = [row for row in results if row.get("refused")]
    print()
    dl.kv("questions scored", len(results))
    dl.kv("refusals", len(refused))
    for row in refused:
        print()
        dl.kv(f"  {row['id']}  question", dl.clip(row["query"], 44), 20)
        dl.kv("  answer", dl.clip(row["answer"], 44), 20)
        dl.kv("  correct chunk was retrieved", row["context_hit"], 20)
        dl.kv("  carried a [n] citation", row["has_citation"], 20)
    print()
    dl.para("Retrieval never failed on this subset - the 'correct chunk retrieved' rate is "
            "1.00 - so both refusals had the answer sitting in the context window and refused "
            "anyway. g0068 asked what an OTP code is and why it must not be shared, and got "
            "back a not-found message, with the definition of OTP in the prompt.")
    print()
    dl.para("The most likely explanation is the prompt itself: SYSTEM_PROMPT rule 2 tells the "
            "model to say it does not know rather than guess, and an 8B model applies that rule "
            "too eagerly. The rule is still worth having - it is what stops problem01 - but it "
            "has a cost, and the cost is measurable at 10 %.")

    dl.section("D. faithfulness is the metric that means something here")
    dl.table(["metric", "value", "what it actually measures"],
             [["faithfulness", summary.get("faithfulness"),
               "answer words present in the retrieved context"],
              ["correctness", summary.get("correctness"),
               "answer words present in the reference answer"],
              ["relevance", summary.get("relevance"),
               "question words present in the answer"]])
    print()
    dl.para("Faithfulness at 0.82 says answers stay close to the retrieved text instead of "
            "drawing on the model's own knowledge, which is the property that matters for a "
            "knowledge base like this one. The other two are word-overlap heuristics wearing "
            "the names of things they do not measure: an answer that is correct but worded "
            "differently from the reference scores low on 'correctness', and a thorough answer "
            "scores low on 'relevance' for being long. Read them as 'did not drift', not as "
            "'was right' - see problem09.")

    dl.section("Cause")
    dl.para("Generation is the one stage where a failure produces a well-formed, confident, "
            "wrong answer instead of an error. Retrieval failing is visible: the wrong text "
            "comes back. Generation failing on correct context is invisible unless something "
            "downstream checks the answer against the context it was given.")

    dl.section("Fix applied in LAB3")
    dl.bullet("CONTEXT_HEADER and QUESTION_HEADER are constants in prompt_templates.py, used "
              "by both the prompt builder and the NoLLM parser.")
    dl.bullet("SYSTEM_PROMPT requires inline [n] citations, so an answer either points at a "
              "retrieved chunk or visibly does not.")
    dl.bullet("eval_generation.py measures faithfulness against the retrieved context and "
              "records the refusals with their question ids, so a refusal can be read rather "
              "than guessed at.")
    dl.bullet("DISCLAIMER is appended to every answer - this is safety-critical subject matter "
              "and an unfaithful answer here has consequences beyond a wrong benchmark number.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/generator.py, src/prompt_templates.py, "
            "evaluation/eval_generation.py")


if __name__ == "__main__":
    run()
