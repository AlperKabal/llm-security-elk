import sys
import os
import numpy as np
from sentence_transformers import SentenceTransformer
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from detection.known_jailbreaks import KNOWN_JAILBREAKS

def generate_and_save_embeddings():
    print("Model yükleniyor...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    print(f"{len(KNOWN_JAILBREAKS)} prompt embedding'e çevriliyor...")
    embeddings = model.encode(KNOWN_JAILBREAKS)

    output_path = os.path.join(os.path.dirname(__file__), "jailbreak_embeddings.npy")
    np.save(output_path, embeddings)

    print(f"Embedding'ler kaydedildi: {output_path}")
    print(f"Shape: {embeddings.shape}")

if __name__ == "__main__":
    generate_and_save_embeddings()