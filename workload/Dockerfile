FROM python:3.10-slim

WORKDIR /app
COPY main.py /app/main.py

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "main.py"]
