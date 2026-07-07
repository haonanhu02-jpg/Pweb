FROM python:3.12-slim

WORKDIR /opt/tender-poc

COPY requirements.txt pyproject.toml ./
COPY src ./src

RUN apt-get update && \
    apt-get install -y --no-install-recommends antiword && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

ENV TENDER_POC_DATA_DIR=/data/tender-poc
ENV PYTHONPATH=/opt/tender-poc/src
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "tender_poc.web_api:app", "--host", "0.0.0.0", "--port", "8000"]
