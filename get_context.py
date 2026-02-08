from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from load_env import  qdrant_url, qdrant_key
import torch
import re
collection_name = "instruction"
torch.set_num_threads(1)

client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_key,
)

model = SentenceTransformer('ai-forever/ru-en-RoSBERTa', cache_folder='/app/hf_cache')
model.to(device="cpu")
model.half()
def search(raw_query):
    query = raw_query
    splitted_query = re.split(r'[,.!\n]|\s+(?:and|plus|и|плюс)\s+', query.lower())
    context_parts = []
    for chunk in splitted_query:
        with torch.no_grad():
            query_embed = model.encode(chunk)
        rr = client.search(
            collection_name=collection_name,
            query_vector=query_embed,
            limit=6,
        )

        for hit in rr:
            if any(word in query.lower() for word in ["address", "location", "contact", "hours"]):
                if hit.score > 0.30:
                    context_parts.append(f"INFO: {hit.payload['text']}")
            elif hit.score > 0.35:
                context_parts.append(f"MENU ITEM: {hit.payload['text']}")

    # print(f"\nВопрос: {query}")
    # print("-" * 30)
    # for res in rr:
    #     print(f"Сходство: {res.score:.2f}")
    #     print(f"Текст: {res.payload['text']}\n")
    return "\n---\n".join(sorted(list(set(context_parts))))

if __name__ == "__main__":
    # test test
    search("I want something with seafood and pesto")
    search("Do you have vegetarian breakfast?")
    search("What is your address?")