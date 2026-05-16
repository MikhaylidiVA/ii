"""
База данных подключение
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from app.core.config import settings
from app.models.database import Base


# Создание движка БД
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

# Сессия
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """Зависимость FastAPI для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Контекстный менеджер для работы с БД вне FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация таблиц БД"""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    # Для тестирования подключения
    with get_db_context() as db:
        result = db.execute("SELECT 1")
        print(f"Database connection successful: {result.scalar()}")
