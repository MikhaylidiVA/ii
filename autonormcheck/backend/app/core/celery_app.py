"""
Celery приложение для асинхронной обработки задач
"""
from celery import Celery
from app.core.config import settings


# Создание Celery приложения
celery_app = Celery(
    'autonormcheck',
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        'app.workers.tasks',
    ],
)

# Конфигурация Celery
celery_app.conf.update(
    # Таймауты
    task_time_limit=300,  # 5 минут максимум на задачу
    task_soft_time_limit=240,  # Мягкий лимит 4 минуты
    
    # Retry логика
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Очереди
    task_create_missing_queues=True,
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'routing_key': 'default',
        },
        'parsing': {
            'exchange': 'parsing',
            'routing_key': 'parsing',
        },
        'ai_analysis': {
            'exchange': 'ai_analysis',
            'routing_key': 'ai_analysis',
        },
        'cleanup': {
            'exchange': 'cleanup',
            'routing_key': 'cleanup',
        },
    },
    
    # Сериализация
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Логирование
    worker_hijack_root_logger=False,
    worker_log_level='INFO',
)


# Расписание периодических задач (опционально)
celery_app.conf.beat_schedule = {
    'cleanup-old-projects-every-day': {
        'task': 'app.workers.tasks.cleanup_old_projects',
        'schedule': 86400.0,  # Раз в сутки
        'options': {'queue': 'cleanup'}
    },
}


if __name__ == '__main__':
    # Для тестирования
    print("Celery app initialized")
    print(f"Broker: {settings.celery_broker}")
    print(f"Backend: {settings.celery_backend}")
