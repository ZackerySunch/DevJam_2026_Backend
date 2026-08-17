from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AgentChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    context: Optional[dict] = None


@router.post("/chat")
async def agent_chat(body: AgentChatRequest):
    """AI Agent 對話與分析介面 (留給 AI Agent 功能實作)"""
    return {
        "status": "success",
        "reply": f"AI Agent 接收到請求: {body.query}",
        "session_id": body.session_id,
    }

