"""
Сервис генерации текстовых эмбеддингов
Использует русскоязычную модель для векторизации нормативных документов
"""
import logging
from typing import Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Сервис для генерации эмбеддингов текста"""
    
    def __init__(self, model_name: str = "cointegrated/rubert-tiny2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
    
    def _load_model(self):
        """Ленивая загрузка модели"""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                logger.info(f"Loading embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name, device=self.device)
                logger.info("Embedding model loaded successfully")
                
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
    
    def embed_text(self, text: str) -> list[float]:
        """
        Генерация эмбеддинга для текста
        
        Args:
            text: Текст для векторизации
        
        Returns:
            Вектор эмбеддинга
        """
        self._load_model()
        
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.tolist()
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Пакетная генерация эмбеддингов
        
        Args:
            texts: Список текстов
            batch_size: Размер батча
        
        Returns:
            Список векторов
        """
        self._load_model()
        
        try:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=batch_size,
                show_progress_bar=True,
            )
            return embeddings.tolist()
        
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Вычисление косинусного сходства между двумя текстами
        
        Args:
            text1: Первый текст
            text2: Второй текст
        
        Returns:
            Коэффициент сходства (0-1)
        """
        emb1 = np.array(self.embed_text(text1))
        emb2 = np.array(self.embed_text(text2))
        
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)
    
    def find_most_similar(
        self,
        query: str,
        candidates: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Поиск наиболее похожих текстов среди кандидатов
        
        Args:
            query: Запрос
            candidates: Кандидаты для сравнения
            top_k: Количество лучших результатов
        
        Returns:
            Список кортежей (индекс, сходство)
        """
        # Эмбеддинг запроса
        query_emb = np.array(self.embed_text(query))
        
        # Эмбеддинги кандидатов (пакетно)
        candidate_embs = np.array(self.embed_texts(candidates))
        
        # Косинусное сходство
        similarities = np.dot(candidate_embs, query_emb) / (
            np.linalg.norm(candidate_embs, axis=1) * np.linalg.norm(query_emb)
        )
        
        # Топ-K индексов
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        return [(int(idx), float(similarities[idx])) for idx in top_indices]


# Глобальный экземпляр (ленивая инициализация)
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(model_name: str = "cointegrated/rubert-tiny2") -> EmbeddingService:
    """Получение экземпляра сервиса эмбеддингов"""
    global _embedding_service
    
    if _embedding_service is None or _embedding_service.model_name != model_name:
        _embedding_service = EmbeddingService(model_name=model_name)
    
    return _embedding_service
