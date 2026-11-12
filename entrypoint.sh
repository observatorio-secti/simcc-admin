#!/bin/sh
set -e

# Executa as migrações do banco de dados
alembic upgrade head

# Executa o bootstrap inicial da aplicação (ex: admin padrão)
python -m src.simcc_admin.bootstrap

# Prefixo de rota (aceita ROOT_PATH ou ADMIN_ROOT_PATH)
EFFECTIVE_ROOT_PATH="${ROOT_PATH:-$ADMIN_ROOT_PATH}"

# Inicia a aplicação
if [ -n "$EFFECTIVE_ROOT_PATH" ]; then
    exec uvicorn --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" --root-path "$EFFECTIVE_ROOT_PATH" src.simcc_admin.app:app
else
    exec uvicorn --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*" src.simcc_admin.app:app
fi