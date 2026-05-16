"""
Redis клиент для кэширования и брокера задач
"""
import redis.asyncio as redis
from app.core.config import settings


# Асинхронный Redis клиент
redis_client = redis.Redis(
    host=settings.REDIS_URL.replace("redis://", "").split(":")[0] if "://" in settings.REDIS_URL else "localhost",
    port=int(settings.REDIS_URL.split(":")[-1].split("/")[0]) if ":" in settings.REDIS_URL else 6379,
    db=0,
    decode_responses=True,
)


async def get_redis() -> redis.Redis:
    """Зависимость для получения Redis клиента"""
    return redis_client


class CacheService:
    """Сервис для работы с кэшем"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def get(self, key: str) -> str | None:
        """Получение значения из кэша"""
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, expire_seconds: int = 3600) -> bool:
        """Установка значения в кэш с TTL"""
        return await self.redis.setex(key, expire_seconds, value)
    
    async def delete(self, key: str) -> int:
        """Удаление ключа из кэша"""
        return await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Проверка существования ключа"""
        return await self.redis.exists(key) > 0
    
    async def get_json(self, key: str) -> dict | list | None:
        """Получение JSON из кэша"""
        import json
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_json(self, key: str, data: dict | list, expire_seconds: int = 3600) -> bool:
        """Установка JSON в кэш"""
        import json
        return await self.set(key, json.dumps(data, ensure_ascii=False), expire_seconds)


cache_service = CacheService(redis_client)
