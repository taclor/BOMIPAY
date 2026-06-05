FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY README.md .
COPY src ./src
COPY scripts ./scripts

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN chmod +x /app/scripts/startup.sh

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV BOMIPAY_ENV=production

ENTRYPOINT ["/app/scripts/startup.sh"]
CMD ["uvicorn", "bomipay.main:app", "--host", "0.0.0.0", "--port", "8080"]
