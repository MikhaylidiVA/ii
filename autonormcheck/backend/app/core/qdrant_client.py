"""
Qdrant клиент для векторного поиска нормативных документов
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.core.config import settings


# Синхронный клиент для инициализации
qdrant_client_sync = QdrantClient(
    url=settings.QDRANT_URL,
    timeout=60,
)

# Асинхронный клиент для запросов
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    timeout=60,
)


COLLECTION_NAME = settings.QDRANT_COLLECTION_NAME
VECTOR_SIZE = 384  # Размер эмбеддинга rubert-tiny2


async def init_qdrant_collection():
    """Инициализация коллекции в Qdrant"""
    try:
        # Проверка существования коллекции
        collections = qdrant_client_sync.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if COLLECTION_NAME not in collection_names:
            # Создание коллекции
            qdrant_client_sync.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
                hnsw_config={
                    "m": 16,
                    "ef_construct": 100,
                },
            )
            
            # Создание индекса для фильтрации по типу документа
            qdrant_client_sync.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="document_type",
                field_schema="keyword",
            )
            
            qdrant_client_sync.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="status",
                field_schema="keyword",
            )
            
            print(f"Collection '{COLLECTION_NAME}' created successfully")
        else:
            print(f"Collection '{COLLECTION_NAME}' already exists")
            
    except Exception as e:
        print(f"Error initializing Qdrant collection: {e}")
        raise


class NormsVectorSearch:
    """Сервис для векторного поиска по нормативным документам"""
    
    def __init__(self, client: QdrantClient):
        self.client = client
    
    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 5,
        document_type: str | None = None,
        status: str = "active",
    ) -> list[dict]:
        """
        Поиск похожих чанков норм
        
        Args:
            query_vector: Вектор запроса
            limit: Количество результатов
            document_type: Фильтр по типу документа (ГОСТ, СП, etc.)
            status: Статус документа (active, archived)
        
        Returns:
            Список результатов с метаданными
        """
        # Построение фильтра
        filter_conditions = []
        
        if status:
            filter_conditions.append(
                FieldCondition(
                    key="status",
                    match=MatchValue(value=status),
                )
            )
        
        if document_type:
            filter_conditions.append(
                FieldCondition(
                    key="document_type",
                    match=MatchValue(value=document_type),
                )
            )
        
        search_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Поиск
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        
        # Форматирование результатов
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            })
        
        return formatted_results
    
    async def upload_norm_chunk(
        self,
        chunk_id: str,
        vector: list[float],
        payload: dict,
    ) -> bool:
        """
        Загрузка чанка нормы в векторную БД
        
        Args:
            chunk_id: Уникальный ID чанка
            vector: Векторное представление
            payload: Метаданные (document_id, content, section, etc.)
        """
        point = PointStruct(
            id=chunk_id,
            vector=vector,
            payload=payload,
        )
        
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )
        
        return True
    
    async def upload_norm_chunks_batch(
        self,
        chunks: list[tuple[str, list[float], dict]],
    ) -> bool:
        """Пакетная загрузка чанков"""
        points = [
            PointStruct(id=chunk_id, vector=vector, payload=payload)
            for chunk_id, vector, payload in chunks
        ]
        
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        
        return True
    
    async def delete_norm_chunk(self, chunk_id: str) -> bool:
        """Удаление чанка из векторной БД"""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector={"points": [chunk_id]},
        )
        return True


norms_search = NormsVectorSearch(qdrant_client_sync)
