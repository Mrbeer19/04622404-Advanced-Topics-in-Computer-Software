# -*- coding: utf-8 -*-
"""Problem 01 - Hallucination, and the failure that is worse than hallucination.

Where it came from
    LAB3 (DL-04), `src/generator.py`.

The course template demonstrates hallucination with a `bad_generate()` that
returns a hard-coded lie. That is the textbook case: the model answers without
evidence, and you can see it happen.

The failure actually hit in LAB3 was the opposite - it was invisible. Two
separate defects combined:

  1. The Ollama placeholder API key was the literal string "ollama-ไม่ใช้-key".
     That string goes into the HTTP `Authorization` header, which the OpenAI SDK
     encodes as ASCII, so every single LLM call raised UnicodeEncodeError.
  2. `Generator.generate()` caught every exception and fell back to returning
     `chunks[0]["answer"]` - and its warning `print` was commented out.

Net effect: with USE_LLM = True the system returned raw retrieved text while
reporting itself as generation, and nothing on screen said so. An ungrounded
answer is at least detectable. A silent fallback is not.

This module reproduces both halves against the real knowledge base.
"""

import data_loader as dl


def retrieve(question, docs, top_k=3):
    """Keyword overlap retrieval - deliberately the same weak scorer as the template."""
    words = [w for w in question.lower().split() if w]
    scored = [(sum(w in doc["text"].lower() for w in words), doc) for doc in docs]
    scored = [pair for pair in scored if pair[0] > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


# --------------------------------------------------------- half 1: no evidence

def ungrounded_generate(context):
    """What a model does when nothing stops it: answer anyway."""
    if not context:
        return ("ให้โอนเงินไปยังบัญชีปลอดภัยของธนาคารก่อน แล้วค่อยติดต่อกลับภายหลัง "
                "(ประโยคนี้ไม่มีอยู่ในฐานความรู้ และเป็นวิธีที่มิจฉาชีพใช้จริง)")
    return context[0]["answer"]


def grounded_generate(context, no_context_message):
    """What LAB3 SYSTEM_PROMPT rule 2 forces instead."""
    if not context:
        return no_context_message
    return context[0]["answer"]


# ------------------------------------------------- half 2: the silent fallback

BROKEN_API_KEY = "ollama-ไม่ใช้-key"   # what the course code shipped
FIXED_API_KEY = "ollama-no-key"        # what LAB3 changed it to


def send_authorization_header(api_key):
    """Reproduce what the HTTP client does with the key: encode it as ASCII."""
    return f"Bearer {api_key}".encode("ascii")


def call_llm(api_key):
    """Stand-in for Generator._call(): fails exactly where the real one failed."""
    send_authorization_header(api_key)
    return "<generated answer from llama3.1:8b>"


def generate_silent(api_key, chunks):
    """The shipped version: swallow the error, return retrieved text, say nothing."""
    try:
        return call_llm(api_key)
    except Exception:
        return chunks[0]["answer"]


def generate_loud(api_key, chunks):
    """The LAB3 version: same fallback, but it announces itself."""
    try:
        return call_llm(api_key)
    except Exception as error:
        print(f"  [llm] Failed to use ollama: {error}")
        print("  [llm] Falling back to retrieved text only.")
        return chunks[0]["answer"]


def run():
    docs = dl.load_qa()
    no_context_message = "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้อง"

    dl.title("PROBLEM 01  Hallucination / answering without evidence")

    dl.section("A. the textbook case - a question outside the knowledge base")
    for label, question in [
        ("outside the KB", "ตั๋วเครื่องบินไปเชียงใหม่ราคาเท่าไหร่"),
        ("inside the KB", "ฟิชชิง (phishing) คืออะไร"),
    ]:
        context = retrieve(question, docs)
        print()
        dl.kv("query", f"{question}   [{label}]", 12)
        dl.kv("retrieved", [dl.clip(d["question"], 46) for d in context] or "nothing", 12)
        dl.kv("ungrounded", dl.clip(ungrounded_generate(context), 110), 12)
        dl.kv("grounded", dl.clip(grounded_generate(context, no_context_message), 110), 12)

    dl.section("B. what LAB3 actually hit - a fallback with no evidence it happened")

    question = "แก๊งคอลเซ็นเตอร์อ้างเป็นตำรวจ ต้องทำอย่างไร"
    context = retrieve(question, docs) or docs[:1]

    print()
    dl.kv("the placeholder key shipped as", repr(BROKEN_API_KEY))
    try:
        send_authorization_header(BROKEN_API_KEY)
        print("  encoding it as an ASCII header: succeeded")
    except UnicodeEncodeError as error:
        print(f"  encoding it as an ASCII header: {type(error).__name__}: {error}")
    print("  -> every LLM call raised before it left the machine")

    print()
    print("  USE_LLM = True, key unfixed, warning commented out (as shipped):")
    answer = generate_silent(BROKEN_API_KEY, context)
    print(f"    answer: {dl.clip(answer, 100)}")
    print("    ^ this is retrieved text, not a generated answer, and nothing said so")

    print()
    print("  USE_LLM = True, key unfixed, warning restored (LAB3 fix, part 1):")
    generate_loud(BROKEN_API_KEY, context)

    print()
    print("  USE_LLM = True, key ASCII (LAB3 fix, part 2):")
    print(f"    answer: {generate_loud(FIXED_API_KEY, context)}")

    dl.section("Cause")
    dl.para("An LLM answers with or without evidence - that is its default behaviour, not a "
            "malfunction. Grounding has to be imposed on it from outside.")
    print()
    dl.para("A blanket `except Exception` that returns something plausible converts every "
            "failure underneath it into a wrong answer with no error attached. The ASCII "
            "header bug would have been a one-line fix if it had been allowed to surface.")

    dl.section("Fix applied in LAB3")
    dl.bullet("SYSTEM_PROMPT rule 2 mandates NO_CONTEXT_MESSAGE when the context is "
              "insufficient; rule 3 mandates an inline [n] citation.")
    dl.bullet("Placeholder key changed to ASCII \"ollama-no-key\".")
    dl.bullet("The two [llm] log lines in generator.py were uncommented, so the fallback "
              "can never be silent again.")
    print()
    dl.para("Measured in LAB3 eval_generation: citation rate 0.90, which is exactly "
            "1 - refusal rate 0.10. Every answer that was written carried a source number; "
            "the only two without one are the two refusals, which have nothing to cite.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/generator.py, src/prompt_templates.py")


if __name__ == "__main__":
    run()
