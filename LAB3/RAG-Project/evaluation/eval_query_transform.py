# Measure whether LLM query transformation helps retrieval.
#
# eval_retrieval.py calls the retriever directly, so it never runs the
# transform step. This script does what RAGPipeline.search_only() does —
# transform the query first, then run the same hybrid retrieval on every
# query that comes back — but keeps a record of what was actually searched.
#
#     none          normalize_query() only — the lookup table, no LLM
#     rewrite       LLM rewrites the question into one clearer question
#     multi_query   LLM writes MULTI_QUERY_COUNT extra phrasings, all searched
#     hyde          LLM writes a hypothetical answer, searched alongside
#
# How to interpret the results:
#   * Transformation should help most where the query and the document share
#     little vocabulary — the slang variant here.
#   * It costs one LLM call per question, so compare the gain against ms/query.
#
# Needs a running LLM (config.LLM_PROVIDER).
# Run: python -m evaluation.eval_query_transform

import json
import time

import config
from evaluation.eval_retrieval import load_golden_set
from evaluation.metrics import average, evaluate_one, print_table

# จำนวนข้อที่จะทดสอบ (None = ทั้งหมด)
LIMIT = None

# natural = เคสที่ใช้ตัดสิน, slang = เคสที่คำถามกับเอกสารใช้คำต่างกันจริง
VARIANTS = ["natural", "slang"]

MODES = ["none", "rewrite", "multi_query", "hyde"]

# LLM ที่ผ่านการปรับความปลอดภัยมา บางครั้งปฏิเสธที่จะแต่งคำตอบสมมติเรื่องกลโกง
# ข้อความปฏิเสธนั้นจะกลายเป็นคำค้นไปเลย จึงต้องนับไว้ด้วย
#
# ต้องจับที่คำขอโทษ ไม่ใช่คำว่า "ไม่สามารถ" เพราะคำถามในชุดข้อมูลนี้เองก็มีคำนั้น
# ("เว็บเทรดที่ถอนเงินไม่ได้") การจับหลวม ๆ จะนับคำค้นที่ปกติดีว่าเป็นการปฏิเสธ
REFUSAL_PHRASES = ["ขอโทษ", "ขออภัย", "ไม่สามารถช่วย",
                   "I cannot", "I can't", "I'm sorry"]


def llm_written(searched, mode):
    """ส่วนของคำค้นที่ LLM เป็นคนเขียน — ตำแหน่งต่างกันในแต่ละโหมด

    rewrite แทนคำถามเดิมทั้งอัน ส่วน multi_query กับ hyde เก็บคำถามเดิมไว้ตัวแรก
    """
    if mode == "none":
        return []
    return searched if mode == "rewrite" else searched[1:]


def looks_like_refusal(text):
    return any(phrase in text for phrase in REFUSAL_PHRASES)


def run_one_mode(rag, items, top_k, mode):
    """ค้นทุกข้อทุก variant ด้วยโหมดแปลงคำถามแบบหนึ่ง"""
    config.USE_QUERY_TRANSFORM = mode != "none"
    config.QUERY_TRANSFORM_MODE = mode

    scores_by_variant = {variant: [] for variant in VARIANTS}
    queries_used = []
    transform_log = []

    for item in items:
        for variant in VARIANTS:
            query = item["variants"].get(variant)
            if not query:
                continue

            searched = rag.transformer.transform(query)
            chunks = rag.retriever.retrieve(
                searched[0], top_k=top_k, extra_queries=searched[1:]
            )
            found = [chunk["chunk_id"] for chunk in chunks]

            scores_by_variant[variant].append(
                evaluate_one(found, item["relevant_chunk_ids"], config.EVAL_K_VALUES)
            )
            queries_used.append(len(searched))
            transform_log.append({
                "id": item["id"],
                "variant": variant,
                "query": query,
                "searched": searched,
                "refused": any(looks_like_refusal(text)
                               for text in llm_written(searched, mode)),
            })

    return scores_by_variant, queries_used, transform_log


def main():
    print("=== วัดผลการแปลงคำถามก่อนค้น ===")

    from src.rag_pipeline import RAGPipeline

    golden = load_golden_set()
    items = golden["items"][:LIMIT] if LIMIT else golden["items"]
    top_k = max(config.EVAL_K_VALUES)
    print(f"จำนวนข้อ: {len(items)} | รูปแบบคำถาม: {', '.join(VARIANTS)}\n")

    # แยกตัวแปรนี้ออกจากตัวแปรอื่น: ปิด rerank และ memory ระหว่างวัด
    original = (config.USE_RERANK, config.USE_MEMORY,
                config.USE_QUERY_TRANSFORM, config.QUERY_TRANSFORM_MODE)
    config.USE_RERANK = False
    config.USE_MEMORY = False

    rag = RAGPipeline()
    print(f"LLM: {config.LLM_PROVIDER} · {rag.generator.llm.model}\n")

    results = {}
    transforms = {}
    for mode in MODES:
        start_time = time.time()
        scores_by_variant, queries_used, transform_log = run_one_mode(
            rag, items, top_k, mode
        )

        # คำค้นที่ LLM คืนมาเป็นข้อความปฏิเสธ ไม่ใช่คำค้นจริง
        refusals = sum(1 for row in transform_log if row["refused"])

        all_scores = [s for scores in scores_by_variant.values() for s in scores]
        results[mode] = {
            "overall": average(all_scores),
            "by_variant": {v: average(s) for v, s in scores_by_variant.items() if s},
            "ms_per_query": round((time.time() - start_time) * 1000 / len(all_scores), 1),
            "avg_queries_searched": round(sum(queries_used) / len(queries_used), 2),
            "llm_refusals": refusals,
        }
        transforms[mode] = transform_log
        print(f"  {mode:12s} เสร็จใน {time.time() - start_time:.1f}s"
              f"{f'  (LLM ปฏิเสธ {refusals} ข้อ)' if refusals else ''}")

    (config.USE_RERANK, config.USE_MEMORY,
     config.USE_QUERY_TRANSFORM, config.QUERY_TRANSFORM_MODE) = original

    # ---------------------------------------------------------- รายงาน
    columns = ["hit@1", f"hit@{top_k}", "mrr", "ndcg@3"]

    print("\n=== ภาพรวม ===")
    print_table({mode: r["overall"] for mode, r in results.items()}, columns)

    for variant in VARIANTS:
        rows = {mode: r["by_variant"].get(variant, {}) for mode, r in results.items()}
        if any(rows.values()):
            print(f"\n=== รูปแบบ: {variant} ===")
            print_table(rows, columns)

    print("\n=== ต้นทุน ===")
    for mode, report in results.items():
        print(f"  {mode:12s} {report['ms_per_query']:9.1f} ms ต่อคำถาม"
              f" | ค้นเฉลี่ย {report['avg_queries_searched']} คำค้นต่อคำถาม"
              f" | LLM ปฏิเสธ {report['llm_refusals']} ข้อ")

    baseline = results["none"]["overall"]["mrr"]
    for mode in MODES[1:]:
        change = (results[mode]["overall"]["mrr"] - baseline) / baseline * 100
        print(f"\n{mode:12s} MRR {results[mode]['overall']['mrr']:.4f}"
              f"  เทียบกับ none {baseline:.4f}  ({change:+.1f}%)")

    with open(config.EVAL_QUERY_TRANSFORM_FILE, "w", encoding="utf-8") as f:
        json.dump({"n_items": len(items), "variants": VARIANTS,
                   "results": results, "transforms": transforms},
                  f, ensure_ascii=False, indent=2)
    print(f"\nบันทึกรายงานที่ {config.EVAL_QUERY_TRANSFORM_FILE}")


if __name__ == "__main__":
    main()
