"""
Agent (功能5: 網路異常診斷 AI Agent), backing routers/agent.py.

Orchestrates the Simaic-hosted agents in agent/call_ai.py:
1. decision(query) -> Simaic decides which real data to pull, but returns it
   as a JSON string whose `message` field ends with an embedded command dict
   (e.g. `{"AP_count": ["5G", "13"], "cable_status": ""}`), sandwiched after
   a human-readable preamble.
2. agent.decoder.decoder(command) -> fetches that data from our own real
   Feature modules (never fabricated).
3. expert(prompt) -> Simaic turns the user's question + the real data into
   a grounded natural-language diagnosis.
"""
import json
import re

from agent.call_ai import decision, expert
from agent.decoder import decoder


def _extract_command(decision_raw: str) -> dict:
    """Pulls the trailing {...} command block out of decision()'s output.
    Simaic's output format isn't fully consistent between calls: sometimes
    it's wrapped in an outer JSON object with the command embedded (escaped)
    inside the `message` field, sometimes it's plain text with the command
    appended directly. Handle both by searching whichever text we land on
    for the last {...} block."""
    try:
        outer = json.loads(decision_raw)
        search_text = outer.get("message") or "" if isinstance(outer, dict) else decision_raw
    except (json.JSONDecodeError, TypeError):
        search_text = decision_raw

    matches = re.findall(r"\{[^{}]*\}", search_text)
    if not matches:
        return {}

    try:
        command = json.loads(matches[-1])
    except json.JSONDecodeError:
        return {}

    return command if isinstance(command, dict) else {}


def diagnose(query: str) -> str:
    """Full pipeline: ask decision what data to pull, pull real data via
    decoder, then ask expert to answer grounded in that data."""
    decision_raw = decision(query)
    command = _extract_command(decision_raw)
    context = decoder(command) if command else {}

    if context:
        prompt = (
            f"使用者問題：{query}\n\n"
            f"後端查詢到的真實資料：\n{json.dumps(context, ensure_ascii=False)}\n\n"
            "請根據以上真實資料，針對使用者的問題給出診斷結論。"
        )
    else:
        prompt = query

    return expert(prompt)
