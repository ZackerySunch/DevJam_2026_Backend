"""
Feature/agent.py
網路異常診斷 AI Agent Pipeline：
1. decision(query) -> SIMAIC decision agent 產出帶有指令的文字/JSON
2. _extract_command(decision_raw) -> 解析出乾淨的 command dict (支援多指令)
3. decoder(command) -> 呼叫後端真實資料 (Feature modules)
4. expert(prompt) -> 結合真實數據生成最終診斷結論
"""
import json
import re
from typing import Optional, Any

from agent.call_ai import decision, expert
from agent.decoder import decoder


def _extract_command(decision_raw: Any) -> dict:
    """
    從 decision 回傳的任意格式（純字串、外層包裝 JSON、Markdown block、多指令區塊）中，
    強力提取出合法的指令字典。
    """
    if not decision_raw:
        return {}

    # 若已是 dict 物件
    if isinstance(decision_raw, dict):
        if "message" in decision_raw and isinstance(decision_raw["message"], str):
            decision_raw = decision_raw["message"]
        else:
            return decision_raw

    if not isinstance(decision_raw, str):
        return {}

    # 1. 嘗試直接將整體解析為 JSON
    try:
        parsed = json.loads(decision_raw)
        if isinstance(parsed, dict):
            # 若外層有 message 欄位且為字串，嘗試往內層解析
            if "message" in parsed and isinstance(parsed["message"], str):
                inner_cmd = _extract_command(parsed["message"])
                if inner_cmd:
                    return inner_cmd
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. 清理 Markdown 程式碼區塊標記 (```json ... ```)
    cleaned_text = re.sub(r"```(?:json)?", "", decision_raw).replace("```", "").strip()

    # 3. 搜尋字串中最外層的所有 {...} 區塊（支援多鍵值與包含列表的結構）
    candidates = re.findall(r"\{[\s\S]*\}", cleaned_text)
    for block in reversed(candidates):
        try:
            cmd = json.loads(block)
            if isinstance(cmd, dict) and cmd:
                return cmd
        except json.JSONDecodeError:
            continue

    # 4. Fallback：單層大括號比對
    single_matches = re.findall(r"\{[^{}]*\}", cleaned_text)
    for block in reversed(single_matches):
        try:
            cmd = json.loads(block)
            if isinstance(cmd, dict) and cmd:
                return cmd
        except json.JSONDecodeError:
            continue

    return {}


def diagnose(query: str, user_data: Optional[dict] = None) -> str:
    """
    Full pipeline: 
    1. 呼叫 decision(query) 判定需要抓取的資料
    2. 解析出指令字典 (例如: {"AP_count": ["5G", "13"], "cable_status": ""})
    3. 傳入 decoder 抓取真實數據
    4. 帶入真實數據後呼叫 expert() 回答
    """
    # 1. 向 Simaic Decision Agent 發送使用者 query
    decision_raw = decision(query)

    print(decision_raw)
    
    # 2. 提取 command 字典
    command = _extract_command(decision_raw)

    print(command)
    
    # 3. 透過 decoder 查詢後端真實數據
    context = decoder(command, user_data=user_data) if command else {}
    print(context)


    # 4. 組裝 prompt 給 expert
    if context:
        prompt = (
            f"使用者問題：{query}\n\n"
            f"後端查詢到的真實資料：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "請根據以上真實資料，針對使用者的問題給出詳細且專業的診斷結論。"
        )
    else:
        prompt = query
    print()

    # 5. 向 Simaic Expert Agent 發送組裝後的 prompt
    return expert(prompt)