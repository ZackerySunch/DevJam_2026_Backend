import requests

# SIMAIC 引擎設定
ENGINE_URL = "https://api.simaic.com/api/run/7a2d9a83-84d1-4e84-a1b6-7bba8b5ab2c9"
API_KEY = "sk_bhf6Vm9fQT9Nm_MKozGJfd_emGG89utc"

# Agent ID 對應表
AGENT_IDS = {
    "decision": "e47bcd96-a7c7-4803-b430-591c2b66a923",
    "expert": "f6c08051-136b-4306-be0e-f492bbdbffe9"
}

# 用於儲存各 Agent 目前對話的 task_id（實現記憶體機制）
session_tasks = {
    "decision": None,
    "expert": None
}

def _call_simaic_api(agent_name, user_message):
    """共用的 API 呼叫核心邏輯"""
    chatbox_id = AGENT_IDS.get(agent_name)
    current_task_id = session_tasks.get(agent_name)
    
    headers = {
        "Content-Type": "application/json",
        "X-Sunch-Key": API_KEY
    }
    
    payload = {
        "chatbox_id": chatbox_id,
        "message": user_message,
        "end_user_id": "default_user",  # 可依需求替換為真實使用者ID
        "task_id": current_task_id
    }
    
    try:
        response = requests.post(ENGINE_URL, json=payload, headers=headers)
        response.raise_for_status()
        res_json = response.json()
        
        if res_json.get("status") == "success":
            data = res_json.get("data", {})
            # 更新並記住最新的 task_id 以維持對話上下文
            session_tasks[agent_name] = data.get("task_id")
            # 回傳回覆內容（支援標準文字或結構化資料）
            return data.get("reply")
        else:
            return f"Error: API returned failure status - {res_json}"
            
    except requests.exceptions.RequestException as e:
        return f"HTTP Request Error: {e}"

def decision(user_message):
    """對應 Decision ChatBox"""
    return _call_simaic_api("decision", user_message)

def expert(prompt):
    """對應 Expert ChatBox"""
    return _call_simaic_api("expert", prompt)