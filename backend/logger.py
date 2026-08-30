import json
import os
from datetime import datetime, timezone

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "logs", "llm_interactions.log")

SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
BEHAVIORAL_SEVERITY_MAP = {"rate_anomaly": "medium", "length_anomaly": "low", "repetition_anomaly": "high",}

def collect_triggered_rule_ids(prompt_detection, response_detection):
    rule_ids = []
    for rule in prompt_detection["triggered_rules"] + response_detection["triggered_rules"]:
        rule_ids.append(rule["rule_id"])
    return rule_ids

def collect_triggered_owasp_categories(prompt_detection, response_detection, behavioral_result, semantic_match):
    categories = set()

    for rule in prompt_detection["triggered_rules"] + response_detection["triggered_rules"]:
        categories.add(rule["category"])

    for anomaly, result in behavioral_result.items():
        if result["owasp_category"]:
            categories.add(result["owasp_category"])

    if semantic_match["owasp_category"]:
        categories.add(semantic_match["owasp_category"])

    return list(categories)

def get_embedding_severity(semantic_match):
    score = semantic_match["similarity_score"]
    if score >= 0.75:
        return "critical"
    elif score >= 0.72:
        return "high"
    elif score >= 0.7:
        return "medium"
    else:
        return "none"

def get_Highest_Behavioral_Anomaly(behavioral_result):
    highest_severity = "none"
    highest_anomaly = None
    for (anomaly, result) in behavioral_result.items():
            if result["flagged"] and SEVERITY_ORDER[BEHAVIORAL_SEVERITY_MAP[anomaly]] > SEVERITY_ORDER[highest_severity]:
                highest_severity = BEHAVIORAL_SEVERITY_MAP[anomaly]
                highest_anomaly = {anomaly: result}
    return highest_anomaly


def calculate_overall_severity(prompt_detection, response_detection, behavioral_result, semantic_match):
    all_rules = prompt_detection["triggered_rules"] + response_detection["triggered_rules"]
        
    overall_severity = "none"
    overall_severity_source = "none"

    if all_rules:
        max_rule = None
        for rule in all_rules:
            if max_rule is None:
                max_rule = rule
            else: 
                if SEVERITY_ORDER[max_rule["severity"]] < SEVERITY_ORDER[rule["severity"]]:
                    max_rule = rule
        overall_severity = max_rule["severity"]
        overall_severity_source = f"rulebook:{max_rule['rule_id']}"
    
    highest_behavioral_anomaly = get_Highest_Behavioral_Anomaly(behavioral_result)
    if highest_behavioral_anomaly:
        for (anomaly, _) in highest_behavioral_anomaly.items():
            if SEVERITY_ORDER[BEHAVIORAL_SEVERITY_MAP[anomaly]] > SEVERITY_ORDER[overall_severity]:
                overall_severity = BEHAVIORAL_SEVERITY_MAP[anomaly]
                overall_severity_source = f"behavioral:{anomaly}"
    embedding_severity = get_embedding_severity(semantic_match)
    if SEVERITY_ORDER[embedding_severity] > SEVERITY_ORDER[overall_severity]:
        overall_severity = embedding_severity
        overall_severity_source = "embedding"
    return overall_severity, overall_severity_source

def log_interaction(event_time,prompt_received_at,user_id, session_id,chat_id,prompt, response,final_response, prompt_detection, response_detection,behavioral_result,semantic_match, blocked, blocked_at,source_ip, source_port, destination_ip, destination_port):
    overall_severity, overall_severity_source = calculate_overall_severity(prompt_detection, response_detection, behavioral_result,semantic_match)
    triggered_rule_ids = collect_triggered_rule_ids(prompt_detection, response_detection)
    triggered_owasp_categories = collect_triggered_owasp_categories(prompt_detection, response_detection, behavioral_result, semantic_match)
    log_entry = {
        "event_timestamp": event_time.isoformat(),
        "prompt_received_at": prompt_received_at.isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "chat_id": chat_id,
        "network": {
            "source_ip": source_ip,
            "source_port": source_port,
            "destination_ip": destination_ip,
            "destination_port": destination_port,
        },
        "prompt": prompt,
        "response": response,
        "final_response": final_response,
        "blocked": blocked,
        "blocked_at": blocked_at,
        "detection": {
            "prompt_detection": prompt_detection,
            "response_detection": response_detection,
            "behavioral_detection": behavioral_result,
            "semantic_match": semantic_match,
        },
        "triggered_owasp_categories": triggered_owasp_categories,
        "triggered_rule_ids": triggered_rule_ids,
        "overall_severity": overall_severity,
        "overall_severity_source": overall_severity_source,
    }
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Error writing log: {e}")

    return log_entry