# AutoNormCheck — Система автоматического анализа проектной документации

## 📋 Описание

AI-система для автоматической проверки проектной документации (PDF, DWG) на соответствие нормативной базе РФ:
- ГОСТ Р 52289, ГОСТ 33150, СП 34.13330, ПДД РФ
- Требования к дорогам, тротуарам, парковкам, инженерным сетям
- Нормы благоустройства (озеленение, освещение, МАФ, доступная среда)

## 🏗 Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│  API Gateway │────▶│ Task Broker │
│  (React TS) │     │   (FastAPI)  │     │  (Celery)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
              ┌─────────────────────────────────┼─────────────────────────────────┐
              │                                 │                                 │
       ┌──────▼──────┐                  ┌──────▼──────┐                  ┌──────▼──────┐
       │   Parsers   │                  │ AI Workers  │                  │   Cleanup   │
       │ PDF + DWG   │                  │ RAG + LLM   │                  │   Worker    │
       └──────┬──────┘                  └──────┬──────┘                  └──────┬──────┘
              │                                 │                                 │
       ┌──────▼─────────────────────────────────▼─────────────────────────────────▼──────┐
       │                              Data Layer                                         │
       │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
       │  │ PostgreSQL  │  │   PostGIS   │  │   Qdrant    │  │    MinIO    │            │
       │  │  (Metadata) │  │ (Geometry)  │  │  (Vectors)  │  │   (Files)   │            │
       │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
       └─────────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Быстрый старт

### Предварительные требования

- Docker ≥ 20.10
- Docker Compose ≥ 2.0
- 8 ГБ RAM (рекомендуется 16 ГБ для AI-моделей)
- 20 ГБ свободного места

### Установка

```bash
# 1. Клонирование репозитория
git clone <repository-url>
cd autonormcheck

# 2. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env при необходимости

# 3. Запуск всех сервисов
docker-compose up -d

# 4. Проверка статуса
docker-compose ps

# 5. Просмотр логов
docker-compose logs -f
```

Сервисы будут доступны по адресам:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Redis Commander**: http://localhost:8081

## 📁 Структура проекта

```
autonormcheck/
├── docker-compose.yml          # Оркестрация сервисов
├── .env.example                # Шаблон переменных окружения
├── README.md                   # Документация
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt        # Python зависимости
│   └── app/
│       ├── main.py             # Точка входа FastAPI
│       ├── core/               # Конфигурация и клиенты
│       │   ├── config.py
│       │   ├── database.py
│       │   ├── redis_client.py
│       │   ├── qdrant_client.py
│       │   ├── minio_client.py
│       │   └── celery_app.py
│       ├── models/             # SQLAlchemy модели
│       │   ├── database.py
│       │   └── schemas.py
│       ├── api/                # REST эндпоинты
│       │   ├── projects.py
│       │   ├── files.py
│       │   ├── issues.py
│       │   ├── auth.py
│       │   └── norms.py
│       ├── services/           # Бизнес-логика
│       │   ├── parsers/
│       │   │   ├── pdf_parser.py
│       │   │   └── dwg_parser.py
│       │   ├── analysis/
│       │   │   ├── norm_checker.py
│       │   │   └── geometry_validator.py
│       │   └── embeddings/
│       │       └── embedding_service.py
│       └── workers/            # Celery задачи
│           └── tasks.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── components/         # UI компоненты
│       ├── pages/              # Страницы
│       ├── hooks/              # Custom hooks
│       └── utils/              # Утилиты
└── scripts/
    ├── init_db.sh
    └── load_norms.py
```

## 🔧 Конфигурация

### Переменные окружения (.env)

```bash
# Database
POSTGRES_USER=autonorm
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=autonormcheck
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Qdrant (Vector DB)
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=norms_collection

# MinIO (S3-compatible storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadminpassword
MINIO_BUCKET=projects

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Models
EMBEDDING_MODEL=sentence-transformers/rubert-tiny2
LLM_MODEL_PATH=/models/llama-3-8b-instruct

# Application
ENVIRONMENT=development
DEBUG=true
FILE_UPLOAD_MAX_SIZE=104857600  # 100MB
DATA_RETENTION_DAYS=7
```

## 📊 API Endpoints

### Проекты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/projects` | Создать проект |
| GET | `/api/v1/projects` | Список проектов |
| GET | `/api/v1/projects/{id}` | Детали проекта |
| DELETE | `/api/v1/projects/{id}` | Удалить проект |

### Файлы

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/files/upload` | Загрузить файл (PDF/DWG) |
| GET | `/api/v1/files/{id}` | Получить информацию о файле |
| GET | `/api/v1/files/{id}/download` | Скачать файл |
| DELETE | `/api/v1/files/{id}` | Удалить файл |

### Замечания

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/issues` | Список замечаний (с фильтрами) |
| GET | `/api/v1/issues/{id}` | Детали замечания |
| PATCH | `/api/v1/issues/{id}/review` | Подтвердить/отклонить |
| GET | `/api/v1/issues/export` | Экспорт (PDF/CSV/JSON) |

### Нормативная база

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/norms/search` | Поиск норм (текст + вектор) |
| GET | `/api/v1/norms/{id}` | Детали нормы |
| POST | `/api/v1/norms/upload` | Загрузить новый документ |

### Анализ

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/analyze/start` | Запустить анализ файла |
| GET | `/api/v1/analyze/status/{task_id}` | Статус обработки |
| GET | `/api/v1/analyze/report/{project_id}` | Получить отчёт |

## 🔍 Пример запроса на анализ

```bash
# 1. Загрузка файла
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@road_project.dwg" \
  -F "project_id=proj_123"

# 2. Запуск анализа
curl -X POST http://localhost:8000/api/v1/analyze/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_ids": ["file_456"], "check_categories": ["road_safety", "accessibility"]}'

# 3. Проверка статуса
curl http://localhost:8000/api/v1/analyze/status/task_789 \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. Получение отчёта
curl http://localhost:8000/api/v1/analyze/report/proj_123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📄 Формат отчёта (JSON Schema)

```json
{
  "project_id": "proj_123",
  "file_name": "road_project.dwg",
  "processed_at": "2024-01-15T10:30:00Z",
  "summary": {
    "total_issues": 15,
    "critical": 3,
    "important": 7,
    "recommendations": 5
  },
  "issues": [
    {
      "id": "issue_001",
      "priority": "CRITICAL",
      "category": "ROAD_SAFETY",
      "title": "Недостаточная ширина пешеходного перехода",
      "description": "Ширина пешеходного перехода составляет 3.5м, что менее требуемых 4.0м согласно ГОСТ Р 52289-2019",
      "regulation_reference": {
        "doc_name": "ГОСТ Р 52289-2019",
        "section": "5.2.4",
        "text": "Минимальная ширина пешеходного перехода должна составлять не менее 4,0 м"
      },
      "suggestion": "Увеличить ширину пешеходного перехода до 4.0м или более",
      "confidence_score": 0.92,
      "location": {
        "type": "Polygon",
        "coordinates": [[[100.5, 200.3], [105.2, 200.3], [105.2, 205.8], [100.5, 205.8], [100.5, 200.3]]],
        "bbox": [100.5, 200.3, 105.2, 205.8]
      },
      "review_status": "PENDING",
      "created_at": "2024-01-15T10:35:00Z"
    }
  ]
}
```

## 🛡 Безопасность и 152-ФЗ

### Реализованные меры

1. **Шифрование данных**
   - TLS 1.3 для всех соединений
   - Шифрование дисков (AES-256)
   - Шифрование S3-бакетов

2. **Изоляция данных**
   - Ephemeral-контейнеры для обработки файлов
   - Сетевая сегментация между сервисами
   - Отдельные VPC для БД и хранилища

3. **Контроль доступа**
   - JWT-аутентификация с коротким временем жизни токенов
   - RBAC (Role-Based Access Control)
   - Логирование всех операций

4. **Жизненный цикл данных**
   - Автоматическое удаление исходников через TTL (настраивается)
   - Очистка временных файлов после обработки
   - Аудит доступа к персональным данным

### Рекомендации для production

- Развертывание в частном облаке или on-premise
- Использование HSM для хранения ключей шифрования
- Регулярное резервное копирование с шифрованием
- Мониторинг аномальной активности

## ⚙️ AI-модули

### Парсинг файлов

| Формат | Библиотеки | Метод |
|--------|-----------|-------|
| PDF | PyMuPDF, PaddleOCR | Векторное извлечение + OCR для растровых слоёв |
| DWG | ODA Converter, ezdxf | Конвертация в DXF → парсинг сущностей |

### RAG-система

- **Векторизация**: `sentence-transformers/rubert-tiny2`
- **Поиск**: Гибридный (BM25 + Dense) через Qdrant
- **Модели**: Локальные Llama-3/Qwen (без внешних API)

### Геометрическая валидация

- **Библиотека**: Shapely + GEOS
- **Проверки**: Расстояния, пересечения, углы, площади
- **Координаты**: Нормализация в WCS, хранение в PostGIS

## 📈 Мониторинг

### Prometheus метрики

- `http_requests_total` — количество запросов
- `file_processing_duration_seconds` — время обработки файлов
- `ai_inference_latency` — задержка AI-инференса
- `celery_tasks_status` — статус задач очереди

### Grafana дашборды

- Общая статистика системы
- Производительность AI-моделей
- Очереди задач и воркеры
- Использование ресурсов

### Логирование

- Структурированные логи (JSON)
- Централизованный сбор через ELK Stack
- Тревоги через Sentry

## 🧪 Тестирование

```bash
# Backend тесты
docker-compose exec backend pytest

# Frontend тесты
docker-compose exec frontend npm test

# Интеграционные тесты
docker-compose exec backend pytest tests/integration/

# Нагрузочное тестирование
docker-compose run locust locust -f tests/load/locustfile.py
```

## 🚀 Production развертывание

### Kubernetes манифесты

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/
kubectl apply -f k8s/ingress.yaml
```

### Масштабирование

```bash
# Увеличение количества AI-воркеров
kubectl scale deployment ai-workers --replicas=10

# Горизонтальное автомасштабирование
kubectl autoscale deployment ai-workers --min=2 --max=20 --cpu-percent=80
```

## 🔧 Troubleshooting

### Проблемы с памятью

```bash
# Проверка использования памяти
docker stats

# Увеличение лимита памяти для контейнера
# В docker-compose.yml добавить:
# deploy:
#   resources:
#     limits:
#       memory: 8G
```

### Ошибки парсинга DWG

- Убедитесь, что ODA File Converter установлен
- Проверьте права доступа к временным файлам
- Для сложных DWG попробуйте конвертировать в DXF вручную

### Медленный AI-инференс

- Используйте GPU (добавьте `deploy.resources.reservations.devices` в docker-compose)
- Уменьшите размер батчей в конфигурации
- Рассмотрите кэширование эмбеддингов

## 📝 Лицензия

Проприетарное ПО. Все права защищены.

## 👥 Контакты

Техническая поддержка: support@autonormcheck.ru
Документация: https://docs.autonormcheck.ru
