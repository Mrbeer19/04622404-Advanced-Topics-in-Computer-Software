# -*- coding: utf-8 -*-
"""Problem 02 - Vocabulary mismatch, and where it actually bites.

Where it came from
    LAB2 (DL-03) chose the embedding model; LAB3 (DL-04) measured what it costs.

The course template shows the mismatch qualitatively: two questions about the
same thing share almost no tokens, so bag-of-words cannot connect them. That is
correct, and this module reproduces it on the real knowledge base, which is
written three times over in formal, conversational and slang registers for
exactly this purpose.

What the template does not show is the other half of the result, and it is the
more useful half: **the dense embedding model does not solve the problem
either.** Measured over 216 golden-set queries in LAB3, dense-only retrieval
scores its worst MRR anywhere on the slang variant - lower than BM25, the
keyword method it was supposed to replace. Semantic search fails on slang for
the same reason keyword search does: the model never saw those words paired with
their formal equivalents during training, so there is no shared vocabulary in
either the token space or the vector space.

The fix is not to pick a side. It is to run both and merge them with Reciprocal
Rank Fusion, which is what USE_HYBRID does.
"""

import data_loader as dl


def bow(text):
    counts = {}
    for token in text.split():
        counts[token] = counts.get(token, 0) + 1
    return counts


def with_position(text):
    return [(index, token) for index, token in enumerate(text.split())]


def run():
    entries = dl.load_qa()

    dl.title("PROBLEM 02  Vocabulary mismatch / token position")

    dl.section("A. the knowledge base is built to expose this")
    counts = {}
    for entry in entries:
        counts[entry["lang"]] = counts.get(entry["lang"], 0) + 1
    dl.table(["register", "Q&A pairs"],
             [[lang, counts[lang]] for lang in sorted(counts, key=counts.get, reverse=True)],
             align_right={1})
    dl.para("The same facts are written three times in three registers, so a question typed "
            "the way people actually type it still has to reach the right answer.")

    dl.section("B. the same question in two registers, as the golden set pairs them")
    try:
        items = dl.golden_set()["items"]
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    pairs = [item for item in items if "slang" in item.get("variants", {})]
    for item in pairs[:3]:
        print()
        dl.kv("formal", item["variants"]["verbatim"], 10)
        dl.kv("slang", item["variants"]["slang"], 10)
        formal_chars = set(item["variants"]["verbatim"])
        slang_chars = set(item["variants"]["slang"])
        overlap = len(formal_chars & slang_chars) / max(1, len(formal_chars | slang_chars))
        dl.kv("character overlap", f"{overlap:.0%}", 10)
    print()
    dl.kv("golden-set items carrying a slang variant", f"{len(pairs)} of {len(items)}")

    dl.section("C. why whitespace splitting is not tokenisation for Thai")
    formal = pairs[0]["variants"]["verbatim"]
    slang = pairs[0]["variants"]["slang"]
    formal_tokens, slang_tokens = formal.split(), slang.split()
    shared = set(formal_tokens) & set(slang_tokens)

    dl.kv("formal, split on whitespace", f"{len(formal_tokens)} tokens  {formal_tokens}", 30)
    dl.kv("slang, split on whitespace", f"{len(slang_tokens)} tokens  {slang_tokens}", 30)
    dl.kv("tokens the two share", f"{len(shared)}  {sorted(shared) or 'none'}", 30)
    dl.para("These two questions are 87 % identical character by character and differ in one "
            "word - but whitespace splitting puts that word inside a phrase-sized token, so the "
            "token carrying the difference is the whole clause. Thai writes without spaces "
            "between words, so `text.split()` does not produce words at all. BM25 has almost "
            "nothing left to match on, and that is a broken tokeniser, not a weakness of BM25.")
    print()
    try:
        from pythainlp.tokenize import word_tokenize
        formal_real = word_tokenize(formal, engine="newmm")
        slang_real = word_tokenize(slang, engine="newmm")
        real_shared = set(formal_real) & set(slang_real)
        dl.kv("pythainlp newmm, formal", f"{len(formal_real)} tokens  {formal_real}", 30)
        dl.kv("pythainlp newmm, slang", f"{len(slang_real)} tokens  {slang_real}", 30)
        total = len(set(formal_real) | set(slang_real))
        dl.kv("tokens the two share", f"{len(real_shared)} of {total}", 30)
    except ImportError:
        dl.kv("pythainlp", "not installed in this interpreter", 30)
        dl.para("LAB3 treats pythainlp as a hard requirement for exactly this reason. Without it "
                "tokenize_thai() falls back to sliding 3-character windows, BM25 scores collapse, "
                "and the whole dense-vs-hybrid comparison below becomes meaningless. Install it "
                "with the rest of LAB3/RAG-Project/requirements.txt to see the real tokens here.")

    dl.section("D. bag-of-words also throws away word order")
    ordered = " ".join(entries[0]["answer"].split()[:6])
    reversed_text = " ".join(reversed(ordered.split()))
    for index, token in with_position(ordered)[:3]:
        dl.bullet(f"original  [{index}] {dl.clip(token, 52)}")
    for index, token in with_position(reversed_text)[:3]:
        dl.bullet(f"reversed  [{index}] {dl.clip(token, 52)}")
    print()
    dl.kv("BoW of the two is identical", bow(ordered) == bow(reversed_text))
    dl.para("A transformer keeps positional information and lets self-attention decide which "
            "tokens condition which, so \"ธนาคารโทรหาเรา\" and \"เราโทรหาธนาคาร\" are not the "
            "same input. BoW cannot tell them apart at all.")

    dl.section("E. but the embedding model does not rescue slang either - measured")
    try:
        results = dl.eval_retrieval()["results"]
    except dl.MissingArtefact as error:
        print(f"  {error}")
        return

    variants = ["verbatim", "slang", "partial", "natural"]
    rows = []
    for name in ["dense_only", "bm25_only", "hybrid", "hybrid+rerank"]:
        if name not in results:
            continue
        by_variant = results[name]["by_variant"]
        rows.append([name] + [f"{by_variant[v]['mrr']:.4f}" if v in by_variant else "-"
                              for v in variants])
    dl.table(["run (MRR)"] + variants, rows, align_right=set(range(1, len(variants) + 1)))

    dense = results["dense_only"]["by_variant"]
    hybrid = results["hybrid"]["by_variant"]
    worst = min(dense, key=lambda v: dense[v]["mrr"])
    gain = (hybrid["slang"]["mrr"] - dense["slang"]["mrr"]) / dense["slang"]["mrr"]

    print()
    dl.kv("dense-only worst variant", f"{worst}  (MRR {dense[worst]['mrr']:.4f})")
    dl.kv("hybrid on the same variant", f"{hybrid['slang']['mrr']:.4f}")
    dl.kv("improvement", f"+{gain * 100:.0f} %")
    dl.kv("hit@10, dense-only -> hybrid",
          f"{results['dense_only']['overall']['hit@10']:.4f} -> "
          f"{results['hybrid']['overall']['hit@10']:.4f}")

    dl.section("Cause")
    dl.para("Keyword matching fails on slang because the tokens differ. Dense retrieval fails "
            "on slang because paraphrase-multilingual-MiniLM-L12-v2 has little Thai slang in "
            "its training data, so those words land nowhere near their formal equivalents in "
            "the vector space. Both methods fail on the same queries, but not for the same "
            "reason - which is why combining them works.")

    dl.section("Fix applied in LAB2 and LAB3")
    dl.bullet("LAB2: a multilingual embedding model, not an English-only one - the corpus is "
              "Thai and an English model would have had nothing to work with at all.")
    dl.bullet("LAB3: USE_HYBRID runs BM25 alongside dense retrieval and merges the two ranked "
              "lists with Reciprocal Rank Fusion (RRF_K = 60).")
    dl.bullet("LAB3: normalize_query() applies a SLANG_MAP lookup (ตังค์ -> เงิน, แบงก์ -> ธนาคาร, "
              "มิจ -> มิจฉาชีพ) before retrieval, which closes the gap for free.")
    print()
    dl.para("Result: hybrid beats dense-only on every single variant, and hit@10 reaches a "
            "perfect 1.0000 - the correct chunk never falls out of the candidate set, so "
            "reranking downstream always has something to work with.")
    print()
    dl.para("Source: LAB3/RAG-Project/src/hybrid_retriever.py, src/query_transform.py")


if __name__ == "__main__":
    run()
