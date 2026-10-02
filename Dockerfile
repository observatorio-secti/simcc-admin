FROM python:3.14-slim

WORKDIR app/
COPY . .

RUN pip install .

EXPOSE 8000
CMD uvicorn --host 0.0.0.0 --port 8000 src.simcc_admin.app:app