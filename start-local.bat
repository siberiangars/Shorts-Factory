@echo off
title Shorts Factory — Local
color 0A

echo.
echo  ╔══════════════════════════════════╗
echo  ║     Shorts Factory  LOCAL        ║
echo  ╚══════════════════════════════════╝
echo.

cd /d "%~dp0"

echo [1/3] Запускаю контейнеры...
docker compose -f docker-compose.local.yml up -d --build

if errorlevel 1 (
    echo.
    echo  ОШИБКА: Docker не запустился.
    echo  Убедись что Docker Desktop открыт и работает.
    pause
    exit /b 1
)

echo.
echo [2/3] Жду готовности API...
:wait_api
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 goto wait_api

echo.
echo [3/3] Применяю миграции БД...
docker compose -f docker-compose.local.yml exec -T api /app/.venv/bin/alembic upgrade head

echo.
echo  ══════════════════════════════════════
echo  ✓  Shorts Factory запущен локально!
echo.
echo  Открой в браузере:  http://localhost:3000
echo  API документация:   http://localhost:8000/docs
echo  ══════════════════════════════════════
echo.

start http://localhost:3000

echo  Нажми любую клавишу для просмотра логов (Ctrl+C для выхода)...
pause >nul

docker compose -f docker-compose.local.yml logs -f
