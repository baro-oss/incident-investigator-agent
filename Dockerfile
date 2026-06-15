FROM python:3.14-slim

WORKDIR /app

# Deps layer (cached khi chỉ đổi code)
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir -e .

# App source
COPY . .

# Tạo thư mục data nếu không mount
RUN mkdir -p data

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=data/investigation.db

CMD ["python", "scripts/start_server.py"]
