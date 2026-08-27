import os
import numpy as np
from sentence_transformers import SentenceTransformer
from detection.known_jailbreaks import KNOWN_JAILBREAKS

EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "embeddings", "jailbreak_embeddings.npy")
SIMILARITY_THRESHOLD = 0.70

_model = None
_jailbreak_embeddings = None

def _load_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('BAAI/bge-base-en-v1.5')
    return _model

def _load_jailbreak_embeddings():
    global _jailbreak_embeddings
    if _jailbreak_embeddings is None:
        _jailbreak_embeddings = np.load(EMBEDDINGS_PATH)
    return _jailbreak_embeddings

def cosine_similarity(a, b):
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def check_semantic_similarity(prompt):
    model = _load_model()
    jailbreak_embeddings = _load_jailbreak_embeddings()

    prompt_embedding = model.encode(prompt)

    best_score = 0.0
    best_match_index = -1
    index = 0
    for jailbreak_embedding in jailbreak_embeddings:
        score = cosine_similarity(prompt_embedding, jailbreak_embedding)
        if score > best_score:
            best_score = score
            best_match_index = index
        index += 1

    flagged = bool(best_score >= SIMILARITY_THRESHOLD)

    if best_match_index >= 0:
        best_match_text = KNOWN_JAILBREAKS[best_match_index]["text"]
        best_match_category = KNOWN_JAILBREAKS[best_match_index]["category"] if flagged else None
    else:
        best_match_text = None
        best_match_category = None

    return {
        "flagged": flagged,
        "similarity_score": round(float(best_score), 3),
        "closest_match_text": best_match_text,
        "owasp_category": best_match_category,
    }