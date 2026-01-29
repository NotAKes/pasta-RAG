from qdrant_client import QdrantClient
from qdrant_client import models
from sentence_transformers import SentenceTransformer
import json


client = QdrantClient(
    url="https://ad3e465b-90fd-499d-8a00-b2c821e79f94.europe-west3-0.gcp.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.ZSZuSXhrQn29gLeyULF-_Hpxh_wiOXU1H1rJB6Nem9U",
)

collection_name = "instruction"

model = SentenceTransformer('ai-forever/ru-en-RoSBERTa')
def upload_menu():
    with open('instruction.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        client.delete_collection(collection_name=collection_name)
        print(f"Старая коллекция {collection_name} удалена.")
    except Exception:
        pass

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE)
    )
    points = []
    for idx, item in enumerate(data):
        vector = model.encode(item['text']).tolist()

        # Создаем "точку" для Qdrant
        points.append(models.PointStruct(
            id=idx,
            vector=vector,
            payload={
                "text": item['text'],
                "metadata": item['metadata']
            }
        ))

    client.upsert(collection_name=collection_name, points=points)
    print(f"Успешно загружено {len(points)} позиций!")


if __name__ == "__main__":
    upload_menu()
