from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from agent import call_ai


router = APIRouter()


class AgentChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    context: Optional[dict] = None


@router.post("/chat")
async def agent_chat(body: AgentChatRequest):
    commamnd = call_ai.decision(user_message)
    data = decoder(command,user_data)
    prompt = build_prompt(user_message,data)
    reply_message = call_ai.expert(prompt)
    return reply_message