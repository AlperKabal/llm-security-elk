import json
import os
from datetime import datetime, timezone

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "logs", "llm_interactions.log")

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

def calculate_overall_severity(prompt_detection, response_detection):
    all_rules = prompt_detection["triggered_rules"] + response_detection["triggered_rules"]
    if not all_rules:
        return "none"

    max_rule = None
    for rule in all_rules:
        if max_rule is None:
            max_rule = rule
        else: 
            if SEVERITY_ORDER[max_rule["severity"]] < SEVERITY_ORDER[rule["severity"]]:
                max_rule = rule
    return max_rule["severity"]

def log_interaction(user_id, session_id, prompt, response, prompt_detection, response_detection,behavioral_result, blocked, blocked_at):
    overall_severity = calculate_overall_severity(prompt_detection, response_detection)
    log_entry = {
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "prompt": prompt,
        "response": response,
        "blocked": blocked,
        "blocked_at": blocked_at,
        "detection": {
            "prompt_detection": prompt_detection,
            "response_detection": response_detection,
            "behavioral_detection": behavioral_result
        },
        "overall_severity": overall_severity,
    }
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Error writing log: {e}")

    return log_entry