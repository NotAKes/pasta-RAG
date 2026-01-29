import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

collection_name = "instruction"

client = QdrantClient(
    url="https://ad3e465b-90fd-499d-8a00-b2c821e79f94.europe-west3-0.gcp.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.ZSZuSXhrQn29gLeyULF-_Hpxh_wiOXU1H1rJB6Nem9U",
)
model = SentenceTransformer('ai-forever/ru-en-RoSBERTa')
def search(raw_query):
    query = raw_query
    query_embed = model.encode(query).tolist()
    rr = client.search(
        collection_name=collection_name,
        query_vector=query_embed,
        limit=6,
    )
    context_parts = []
    for hit in rr:
        if any(word in query.lower() for word in ["address", "location", "contact", "hours"]):
            if hit.score > 0.30:
                context_parts.append(f"INFO: {hit.payload['text']}")
        elif hit.score > 0.35:
            context_parts.append(f"MENU ITEM: {hit.payload['text']}")
    print(f"\nВопрос: {query}")
    print("-" * 30)
    for res in rr:
        print(f"Сходство: {res.score:.2f}")
        print(f"Текст: {res.payload['text']}\n")
    return "\n---\n".join(context_parts)

if __name__ == "__main__":
    # test test
    search("I want something with seafood and pesto")
    search("Do you have vegetarian breakfast?")
    search("What is your address?")