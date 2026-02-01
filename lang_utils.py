import json

from qdrant_client import QdrantClient
from qdrant_client import models
from sentence_transformers import SentenceTransformer
from load_env import  qdrant_url, qdrant_key

client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_key,
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
