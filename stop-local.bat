@echo off
title Shorts Factory — Stop
color 0C

cd /d "%~dp0"

echo.
echo  Останавливаю Shorts Factory...
echo.

docker compose -f docker-compose.local.yml down

echo.
echo  ✓ Все контейнеры остановлены.
echo  Данные (БД, видео) сохранены.
echo.
pause
