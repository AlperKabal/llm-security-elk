import time
from difflib import SequenceMatcher

_user_history={}
RATE_WINDOW_SECONDS = 60
RATE_THRESHOLD = 4

LENGTH_THRESHOLD = 2000

REPETITION_SIMILARITY_THRESHOLD = 0.9
REPETITION_WINDOW_SECONDS = 30
REPETITION_MIN_OCCURRENCES = 3

BEHAVIORAL_OWASP_CATEGORY = "LLM06_Unbounded_Consumption"

def _cleanup_old_entries(user_id):
    now = time.time()
    _user_history[user_id] = [(timestamp, prompt) for (timestamp,prompt) in _user_history[user_id] if now - timestamp <= RATE_WINDOW_SECONDS]

def check_rate_anomaly(user_id):
    if user_id not in _user_history:
        return {"flagged": False, "requests_in_window": 0, "owasp_category": None}
    
    _cleanup_old_entries(user_id)

    count = len(_user_history[user_id])
    return {"flagged": count >= RATE_THRESHOLD, "requests_in_window": count, "owasp_category": BEHAVIORAL_OWASP_CATEGORY if count >= RATE_THRESHOLD else None}

def check_length_anomaly(prompt):
    length = len(prompt)
    return {"flagged": length >= LENGTH_THRESHOLD, "length": length, "owasp_category": BEHAVIORAL_OWASP_CATEGORY if length >= LENGTH_THRESHOLD else None}

def check_repetition(user_id, prompt):
    if user_id not in _user_history:
        return {"flagged": False, "similarity_score": 0.0, "similar_count": 0, "owasp_category": None}

   
    recent_prompts = [p for (ts, p) in _user_history[user_id] if time.time() - ts <= REPETITION_WINDOW_SECONDS]

    similar_count = 0
    max_similarity = 0.0
    for old_prompt in recent_prompts:
        score = SequenceMatcher(None, prompt, old_prompt).ratio()
        max_similarity = max(max_similarity, score)
        if score >= REPETITION_SIMILARITY_THRESHOLD:
            similar_count += 1

    return {
        "flagged": similar_count >= REPETITION_MIN_OCCURRENCES - 1,
        "similarity_score": round(max_similarity, 2),
        "similar_count": similar_count,
        "owasp_category": BEHAVIORAL_OWASP_CATEGORY if similar_count >= REPETITION_MIN_OCCURRENCES - 1 else None
    }

def record_request(user_id, prompt):
    if user_id not in _user_history:
        _user_history[user_id] = [(time.time(),prompt)]
    else:
        _user_history[user_id].append((time.time(),prompt))

def run_behavioral_checks(user_id, prompt):

    rate_result = check_rate_anomaly(user_id)
    length_result = check_length_anomaly(prompt)
    repetition_result = check_repetition(user_id, prompt)
    record_request(user_id, prompt)

    return {
        "rate_anomaly": rate_result,
        "length_anomaly": length_result,
        "repetition_anomaly": repetition_result,
    }