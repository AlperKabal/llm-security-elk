from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from detection.detect import detect_prompt, detect_response
from logger import log_interaction, get_Highest_Behavioral_Anomaly
from detection.behavioral import run_behavioral_checks


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

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    prompt: str

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

def askOllama(prompt):
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    })
    return response.json()["response"]


@app.post("/chat")
def post_message(request: ChatRequest):
    user_id = request.user_id
    session_id = request.session_id
    prompt = request.prompt

    prompt_detection = detect_prompt(prompt)
    behavioral_result = run_behavioral_checks(user_id, prompt)
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
    else:
        response = askOllama(prompt)
        response_detection = detect_response(response)
        if severityCheck(response_detection):
            final_response = "Something went wrong. Please try again."
            blocked = True
            blocked_at = "response_stage"
        else: 
            final_response = response
            blocked = False

    log_interaction(user_id,session_id,prompt,response,final_response,prompt_detection,response_detection,behavioral_result,blocked,blocked_at)

    return {"response": final_response}
    

    