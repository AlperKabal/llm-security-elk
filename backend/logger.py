import json
import os
from datetime import datetime, timezone

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "logs", "llm_interactions.log")

SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
BEHAVIORAL_SEVERITY_MAP = {"rate_anomaly": "medium", "length_anomaly": "low", "repetition_anomaly": "high",}

def get_Highest_Behavioral_Anomaly(behavioral_result):
    highest_severity = "none"
    highest_anomaly = None
    for (anomaly, result) in behavioral_result.items():
            if result["flagged"] and SEVERITY_ORDER[BEHAVIORAL_SEVERITY_MAP[anomaly]] > SEVERITY_ORDER[highest_severity]:
                highest_severity = BEHAVIORAL_SEVERITY_MAP[anomaly]
                highest_anomaly = {anomaly: result}
    return highest_anomaly


def calculate_overall_severity(prompt_detection, response_detection, behavioral_result):
    all_rules = prompt_detection["triggered_rules"] + response_detection["triggered_rules"]
        
    overall_severity = "none"
    if all_rules:
        max_rule = None
        for rule in all_rules:
            if max_rule is None:
                max_rule = rule
            else: 
                if SEVERITY_ORDER[max_rule["severity"]] < SEVERITY_ORDER[rule["severity"]]:
                    max_rule = rule
        overall_severity = max_rule["severity"]
    
    highest_behavioral_anomaly = get_Highest_Behavioral_Anomaly(behavioral_result)
    if highest_behavioral_anomaly:
        for (anomaly, _) in highest_behavioral_anomaly.items():
            if SEVERITY_ORDER[BEHAVIORAL_SEVERITY_MAP[anomaly]] > SEVERITY_ORDER[overall_severity]:
                overall_severity = BEHAVIORAL_SEVERITY_MAP[anomaly]

    return overall_severity

def log_interaction(user_id, session_id, prompt, response,final_response, prompt_detection, response_detection,behavioral_result, blocked, blocked_at):
    overall_severity = calculate_overall_severity(prompt_detection, response_detection, behavioral_result)
    log_entry = {
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "prompt": prompt,
        "response": response,
        "final_response": final_response,
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