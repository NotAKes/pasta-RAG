from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from load_env import  qdrant_url, qdrant_key
import torch
import re
import os
import json
from qdrant_client.models import VectorParams, Distance, PointStruct
collection_name = "instruction_"
torch.set_num_threads(1)

client = QdrantClient(
    host="qdrant",
    port=6333
)

model = SentenceTransformer('ai-forever/ru-en-RoSBERTa', cache_folder='/app/hf_cache')
model.to(device="cpu")
model.half()

def sync_menu_to_qdrant():
    """Синхронизирует instruction.json с коллекцией в Qdrant"""
    json_path = 'instruction.json' #
    
    if not os.path.exists(json_path):
        print(f"⚠️ Файл {json_path} не найден.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        new_menu_data = json.load(f)

    # Проверяем текущее состояние коллекции
    try:
        collection_info = client.get_collection(collection_name=collection_name)
        points_count = collection_info.points_count
    except Exception:
        # Если коллекции не существует — создаем её
        points_count = -1

    # Если данные изменились (по количеству), пересоздаем коллекцию
    if points_count != len(new_menu_data):
        print(f"🔄 Обнаружены изменения в меню. Пересоздаем коллекцию '{collection_name}'...")
        
        # Пересоздаем коллекцию с вектором 1024 (размерность RoSBERTa)
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

        # Генерируем векторы и загружаем данные
        points = []
        for idx, item in enumerate(new_menu_data):
            # Используем поле 'text' для создания векторного эмбеддинга
            text_to_encode = item.get('text', '')
            vector = model.encode(text_to_encode).tolist()
            
            points.append(PointStruct(
                id=idx,
                vector=vector,
                payload=item # Сохраняем весь объект, включая metadata
            ))

        # Загружаем пачкой для скорости
        client.upsert(collection_name=collection_name, points=points)
        print(f"✅ Успешно загружено {len(points)} позиций меню в Qdrant.")
    else:
        print(f"✔️ База Qdrant актуальна. Индексация не требуется.")

# Вызываем синхронизацию ПЕРЕД тем, как бот начнет принимать запросы
sync_menu_to_qdrant()

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
