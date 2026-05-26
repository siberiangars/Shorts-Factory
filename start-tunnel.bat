@echo off
setlocal

cd /d "%~dp0"

echo Starting Shorts Factory for Cloudflare Tunnel...
docker compose -f docker-compose.local.yml -f docker-compose.tunnel.yml up -d --build

echo.
echo Applying database migrations...
docker compose -f docker-compose.local.yml -f docker-compose.tunnel.yml exec -T api alembic upgrade head

echo.
echo Starting Cloudflare Tunnel for https://shorts.v3techbots.online
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --config "C:\Users\siber\.cloudflared\shorts-factory.yml" run
