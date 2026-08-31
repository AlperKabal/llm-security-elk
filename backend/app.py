from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from detection.detect import detect_prompt, detect_response
from logger import log_interaction, get_Highest_Behavioral_Anomaly
from detection.behavioral import run_behavioral_checks
from detection.embedding import check_semantic_similarity
from db import init_db,get_all_users,create_user,get_user_chats,create_chat,get_chat_messages,save_message,delete_chat,get_recent_messages
from typing import Optional
from datetime import datetime, timezone


app = FastAPI()
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()



BEHAVIORAL_MESSAGES = {
    "repetition_anomaly": "You seem to be repeating the same request. Please rephrase or wait a moment before trying again.",
    "rate_anomaly": "You're sending requests too quickly. Please slow down.",
    "length_anomaly": "Your prompt is too long. Please shorten your request.",
}

def get_behavioral_block_message(behavioral_result):
    highest_anomaly = get_Highest_Behavioral_Anomaly(behavioral_result)
    if highest_anomaly:
        for(anomaly, _) in highest_anomaly.items():
            return BEHAVIORAL_MESSAGES[anomaly]
    return None

def severityCheck(detection_result):
    for rule in detection_result["triggered_rules"]:
        if rule["severity"] in {"high", "critical"}:
            return True
    return False

def build_prompt_with_history(chat_id, new_prompt):
    if chat_id is None:
        return new_prompt  

    history = get_recent_messages(chat_id, limit=10)
    if not history:
        return new_prompt

    context_lines = []
    for role, content in history:
        speaker = "User" if role == "user" else "Assistant"
        context_lines.append(f"{speaker}: {content}")

    context_text = "\n".join(context_lines)
    return f"{context_text}\nUser: {new_prompt}"

def askOllama(prompt):
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    })
    return response.json()["response"]

@app.get("/users")
def list_users():
    return get_all_users()


class AddUserRequest(BaseModel):
    user_id: str


@app.post("/users")
def add_user(request: AddUserRequest):
    created = create_user(request.user_id)
    if not created:
        return {"error": "User already exists"}, 409
    return {"user_id": request.user_id}

@app.get("/chats")
def list_chats(user_id: str):
    return get_user_chats(user_id)


@app.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    return get_chat_messages(chat_id)


@app.delete("/chats/{chat_id}")
def remove_chat(chat_id: str):
    delete_chat(chat_id)
    return {"status": "deleted"}


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    chat_id: Optional[str] = None
    prompt: str

@app.post("/chat")
def post_message(request: ChatRequest, req: Request):
    prompt_received_at = datetime.now(timezone.utc)
    user_id = request.user_id
    session_id = request.session_id
    chat_id = request.chat_id
    prompt = request.prompt

    source_ip = req.client.host
    source_port = req.client.port
    destination_ip, destination_port = req.scope["server"]

    if chat_id is None:
        title = prompt[:50]
        chat_id = create_chat(user_id, title)

    prompt_detection = detect_prompt(prompt)
    behavioral_result = run_behavioral_checks(user_id, prompt)
    semantic_match = check_semantic_similarity(prompt)

    blocked_at = None
    if severityCheck(prompt_detection):
        final_response = "Something went wrong. Please try again."
        blocked = True
        response = None
        blocked_at = "prompt_stage"
        response_detection = {"triggered_rules": [], "rule_count": 0}
    elif (behavioral_message := get_behavioral_block_message(behavioral_result)):
        final_response = behavioral_message
        blocked = True
        blocked_at = "behavioral_stage"
        response = None
        response_detection = {"triggered_rules": [], "rule_count": 0}
    elif semantic_match["similarity_score"] >= 0.72:
        final_response = "Something went wrong. Please try again."
        blocked = True
        blocked_at = "embedding_stage"
        response = None
        response_detection = {"triggered_rules": [], "rule_count": 0}
    else:
        prompt_with_history = build_prompt_with_history(chat_id, prompt)
        response = askOllama(prompt_with_history)
        response_detection = detect_response(response)
        if severityCheck(response_detection):
            final_response = "Something went wrong. Please try again."
            blocked = True
            blocked_at = "response_stage"
        else: 
            final_response = response
            blocked = False

    event_time = datetime.now(timezone.utc)
    log_interaction(event_time,prompt_received_at, user_id,session_id,chat_id,prompt,response,final_response,prompt_detection,response_detection,behavioral_result,semantic_match,blocked,blocked_at,source_ip, source_port, destination_ip, destination_port)

    save_message(chat_id, "user", user_id, prompt, False, prompt_received_at)
    save_message(chat_id, "assistant", "assistant", final_response, blocked,event_time)

    return {"final_response": final_response, "blocked": blocked, "chat_id": chat_id, "event_time": event_time.isoformat()}
    

    