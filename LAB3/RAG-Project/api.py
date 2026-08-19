


# api.py
# เปิดระบบ RAG ตัวเดิมออกมาเป็นเว็บ ไม่ได้สร้าง AI หรือ pipeline ใหม่
#
#   Browser (web/)  →  POST /api/ask  →  RAGPipeline.ask()  →  answer + sources
#
# ทุกอย่างที่เว็บใช้ คือของเดิมทั้งหมด:
#   src/rag_pipeline.py  ค้น + เขียนคำตอบ
#   src/memory.py        จำบทสนทนา (แยกตาม session ของแต่ละเบราว์เซอร์)
#   config.py            สวิตช์ทุกตัวยังอยู่ที่เดิม
#
# LLM ถูกเรียกจากฝั่ง server เท่านั้น — เบราว์เซอร์ไม่เห็น API key และไม่ได้ต่อกับ LLM โดยตรง
#
# วิธีรัน:
#   1. python build_index.py     (ถ้ายังไม่เคยสร้าง index)
#   2. python api.py             แล้วเปิด http://127.0.0.1:8000

import os
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
from src import index_meta
from src.memory import ConversationMemory
from src.rag_pipeline import RAGPipeline

WEB_DIR = os.path.join(config.BASE_DIR, "web")

MAX_QUESTION_CHARS = 1000   # กันคำถามยาวผิดปกติ
MAX_SESSIONS = 200          # กันหน่วยความจำโตไม่จำกัดเมื่อมีผู้ใช้หลายคน

# สถานะของ server — โหลดโมเดลครั้งเดียวตอนเปิด ไม่ใช่ทุกคำถาม
state = {"rag": None, "ready": False, "error": ""}

# RAGPipeline มี memory ก้อนเดียว แต่เว็บมีผู้ใช้ได้หลายคน
# จึงเก็บ memory แยกตาม session แล้วสลับเข้าไปตอนถาม โดยมี lock กันชนกัน
sessions = OrderedDict()    # session_id -> ConversationMemory
lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    if not os.path.exists(config.FAISS_INDEX_FILE):
        state["error"] = "ยังไม่มี index — ให้รัน python build_index.py ก่อน"
        print(f"[api] {state['error']}")
    else:
        index_meta.warn_if_stale()
        print("[api] กำลังโหลดโมเดลและ index ...")
        try:
            state["rag"] = RAGPipeline()
            state["ready"] = True
            print("[api] พร้อมใช้งาน  →  http://127.0.0.1:8000")
        except Exception as error:
            state["error"] = f"เริ่มระบบไม่สำเร็จ: {error}"
            print(f"[api] {state['error']}")
    yield


app = FastAPI(title="RAG AI Assistant", lifespan=lifespan)


# ---------------------------------------------------------------- error shape
# ทุก error ตอบกลับเป็น JSON รูปแบบเดียวกันเสมอ ฝั่งหน้าเว็บจะได้อ่านง่าย
@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    print(f"[api] ข้อผิดพลาดที่ไม่คาดคิด: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์ กรุณาลองใหม่อีกครั้ง"},
    )


# ---------------------------------------------------------------- data models
class AskRequest(BaseModel):
    question: str = Field(default="")
    session_id: str = Field(default="")


class ClearRequest(BaseModel):
    session_id: str = Field(default="")


def get_memory(session_id):
    """หา memory ของ session นี้ ถ้ายังไม่มีก็สร้างใหม่"""
    if session_id in sessions:
        sessions.move_to_end(session_id)
        return sessions[session_id]

    while len(sessions) >= MAX_SESSIONS:
        sessions.popitem(last=False)

    sessions[session_id] = ConversationMemory()
    return sessions[session_id]


# ---------------------------------------------------------------- API
@app.get("/api/health")
def health():
    """ให้หน้าเว็บเช็คได้ว่าระบบพร้อมหรือยัง และตอนนี้เปิดขั้นตอนไหนอยู่บ้าง"""
    return {
        "ready": state["ready"],
        "error": state["error"],
        "model": config.LLM_PROVIDERS[config.LLM_PROVIDER][1] if config.USE_LLM else "ไม่ใช้ LLM",
        "settings": {
            "hybrid": config.USE_HYBRID,
            "rerank": config.USE_RERANK,
            "query_transform": config.USE_QUERY_TRANSFORM,
            "memory": config.USE_MEMORY,
            "llm": config.USE_LLM,
            "top_k": config.TOP_K,
        },
    }


@app.post("/api/ask")
def ask(payload: AskRequest = Body(...)):
    if not state["ready"]:
        raise HTTPException(503, state["error"] or "ระบบยังไม่พร้อมใช้งาน")

    question = (payload.question or "").strip()

    # 1) คำถามว่าง
    if not question:
        raise HTTPException(400, "กรุณาพิมพ์คำถามก่อนกดส่ง")

    # 2) คำถามยาวเกินไป
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(
            400, f"คำถามยาวเกินไป (จำกัด {MAX_QUESTION_CHARS} ตัวอักษร)"
        )

    session_id = (payload.session_id or "").strip() or uuid.uuid4().hex
    memory = get_memory(session_id)

    # pipeline ตัวเดียวใช้ร่วมกันทุก request จึงต้องล็อกตอนสลับ memory
    started = time.time()
    with lock:
        rag = state["rag"]
        rag.memory = memory
        try:
            result = rag.ask(question)
        except Exception as error:
            print(f"[api] ตอบคำถามไม่สำเร็จ: {error}")
            raise HTTPException(502, f"ระบบตอบคำถามไม่สำเร็จ: {error}")

    # 3) กันกรณี pipeline คืนค่าผิดรูป หรือ LLM ไม่ตอบอะไรกลับมาเลย
    answer = (result or {}).get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(502, "AI ไม่ได้ตอบกลับ กรุณาลองถามใหม่อีกครั้ง")

    return {
        "answer": answer,
        "sources": result.get("sources") or [],
        "no_context": bool(result.get("no_context")),
        "session_id": session_id,
        "elapsed": round(time.time() - started, 2),
        "timings": result.get("timings") or {},
    }


@app.post("/api/clear")
def clear(payload: ClearRequest = Body(...)):
    """ล้างความจำฝั่ง server ของ session นี้ (หน้าเว็บล้างฝั่งตัวเองเพิ่มเอง)"""
    session_id = (payload.session_id or "").strip()
    if session_id in sessions:
        sessions[session_id].clear()
    return {"cleared": True, "session_id": session_id}


# ---------------------------------------------------------------- static web
@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
