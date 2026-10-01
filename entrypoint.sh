#!/bin/sh

# Executa as migrações do banco de dados
alembic upgrade head

# Executa o bootstrap inicial da aplicação (ex: admin padrão)
python -m src.simcc_admin.bootstrap

# Inicia a aplicação
uvicorn --host 0.0.0.0 --port 8000 src.simcc_admin.app:app