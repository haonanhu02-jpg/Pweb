FROM crawlabteam/crawlab:latest

USER root

COPY requirements.txt /tmp/tender-poc-requirements.txt

RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
      apt-get update; \
      apt-get install -y --no-install-recommends antiword; \
      rm -rf /var/lib/apt/lists/*; \
    fi; \
    if command -v python3 >/dev/null 2>&1; then PYTHON_BIN=python3; else PYTHON_BIN=python; fi; \
    "$PYTHON_BIN" -m pip install --no-cache-dir -r /tmp/tender-poc-requirements.txt; \
    mkdir -p /var/log/crawlab; \
    rm -f /tmp/tender-poc-requirements.txt
