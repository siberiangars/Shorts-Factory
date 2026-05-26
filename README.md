# Shorts Factory

Автоматический сервис генерации и постинга YouTube Shorts:
**тема → скрипт (Claude) → голос (ElevenLabs) → B-roll (Pexels) → монтаж 9:16 (FFmpeg) → YouTube**.

## Стек

| Слой | Технология |
|---|---|
| API | Python 3.11 + FastAPI |
| Очередь | Celery + Redis |
| БД | PostgreSQL 16 + SQLAlchemy 2 |
| Фронтенд | Next.js 14 + TypeScript + Tailwind + shadcn/ui |
| LLM | Anthropic Claude API |
| TTS | ElevenLabs |
| Видео | FFmpeg 6 |
| YouTube | Google Data API v3 + OAuth 2.0 |

---

## Установка

### 1. Клонируем и настраиваем окружение

```bash
git clone <repo-url> shorts-factory
cd shorts-factory

cp .env.example .env
```

Заполняем `.env`:

```bash
# Генерация FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Генерация API_AUTH_TOKEN
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Обязательные ключи:
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `ELEVENLABS_API_KEY` — [elevenlabs.io](https://elevenlabs.io)
- `PEXELS_API_KEY` — [pexels.com/api](https://www.pexels.com/api/)

### 2. Подключение YouTube

1. В [Google Cloud Console](https://console.cloud.google.com) создай проект, включи **YouTube Data API v3**.
2. Создай **OAuth 2.0 Client ID** (тип: Web Application).
3. В Authorized redirect URIs добавь: `http://localhost:8000/api/channels/oauth-callback`.
4. Скачай `client_secret.json`, положи в папку `secrets/` рядом с `docker-compose.yml`.

### 3. Запуск

```bash
docker compose up -d --build

# Применить миграции БД
docker compose exec api alembic upgrade head
```

Сервисы:
- **Frontend**: http://localhost:3000
- **API docs (Swagger)**: http://localhost:8000/docs
- **Metrics (Prometheus)**: http://localhost:8000/metrics

### 4. Запуск первого видео

1. Открой http://localhost:3000/channels → **«Создать канал»**.
2. Заполни: название, ниша (например: «биохакинг и здоровье»), язык `ru`, `voice_id` из ElevenLabs.
3. Нажми **«Подключить YouTube»** → пройди OAuth.
4. Перейди на http://localhost:3000/topics → **«Добавить тему»** или **«AI-генерация»**.
5. Нажми **«Запустить»** — pipeline запустится немедленно.
6. Следи за прогрессом на http://localhost:3000/videos.

---

## Масштабирование (несколько GCP-проектов)

YouTube Data API даёт 10 000 единиц в день на проект → ~6 загрузок (`videos.insert` = 1 600 единиц).

Для масштабирования:
1. Создай несколько GCP-проектов, у каждого свой `client_secret.json`.
2. При создании канала укажи `google_cloud_project_id`.
3. Положи соответствующий `client_secret_{project_id}.json` в `secrets/`.
4. Worker автоматически подбирает нужный файл по `channel.google_cloud_project_id`.

---

## Troubleshooting

| Проблема | Решение |
|---|---|
| `FERNET_KEY` ошибка | Убедись что ключ 32 байта, base64-encoded (результат `Fernet.generate_key()`) |
| `alembic upgrade` не находит таблицы | Проверь `DATABASE_URL` и что postgres healthy: `docker compose ps` |
| ElevenLabs 401 | Проверь `ELEVENLABS_API_KEY`, убедись что лимит символов не исчерпан |
| FFmpeg ошибка в воркере | `docker compose logs worker` — обычно проблема с путями или codec |
| YouTube quota exceeded | Проверь `channel.daily_upload_count` в БД; квота сбрасывается в 00:00 UTC |
| OAuth callback ошибка | Убедись что `YOUTUBE_OAUTH_REDIRECT_URI` совпадает с настройками в GCP Console |

---

## Разработка

```bash
# Запуск тестов
docker compose exec api pytest tests/ -v --cov=pipeline --cov-report=term-missing

# Применить новую миграцию
docker compose exec api alembic revision --autogenerate -m "описание изменений"
docker compose exec api alembic upgrade head

# Принудительный запуск пайплайна для topic_id=1
docker compose exec api python -c "
from workers.tasks import process_topic
process_topic.delay(1)
"
```
