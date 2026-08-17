from typing import Optional
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent import call_ai
from agent.decoder import decoder

router = APIRouter()


class AgentChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    context: Optional[dict] = None


def build_prompt(user_message: str, data: dict) -> str:
    """
    將使用者訊息與 decoder 檢索出的真實資料整合成 Expert Prompt。
    """
    summaries = []
    for feat, info in data.items():
        if isinstance(info, dict) and "summary" in info:
            summaries.append(f"- 【{feat}】: {info['summary']}")

    summary_text = "\n".join(summaries) if summaries else "無額外後端數據需求。"
    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    prompt = f"""
使用者提出的問題：
「{user_message}」

【後端系統檢索資料摘要】
{summary_text}

【詳細資料 JSON】
{data_json}

請扮演 HolyPing 專業網路通訊顧問，根據上述真實數據，以繁體中文為使用者提供專業、客觀且有行動建議的完整解答。
"""
    return prompt.strip()


@router.post("/chat")
async def agent_chat(body: AgentChatRequest):
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="query 不能為空")

    user_message = body.query.strip()
    user_data = body.context or {}

    # 1. 意圖與額外資訊判斷
    command = call_ai.decision(user_message)

    # 2. 資料解碼與調用
    data = decoder(command, user_data)

    # 3. 提示詞組裝
    prompt = build_prompt(user_message, data)

    # 4. 專家推論回覆
    reply_message = call_ai.expert(prompt)

    return {
        "status": "success",
        "reply": reply_message,
        "command": command,
        "data": data,
        "session_id": body.session_id,
    }