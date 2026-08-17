from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Feature.agent import diagnose

router = APIRouter()


class ChatRequest(BaseModel):
    query: str  # e.g. "台北網路為什麼很慢？", "哪裡斷線了？"


@router.post("/chat")
async def chat(body: ChatRequest):
    """網路異常診斷 AI Agent：綜合海纜事故與即時流量資料回答問題。"""
    answer = diagnose(body.query)
    # agent/call_ai.py doesn't raise on failure, it returns an error string.
    if isinstance(answer, str) and (answer.startswith("Error:") or answer.startswith("HTTP Request Error:")):
        raise HTTPException(status_code=502, detail=answer)
    return {"answer": answer}
