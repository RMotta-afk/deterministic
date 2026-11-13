FROM node:22-bookworm-slim AS node-runtime

FROM python:3.13-slim-bookworm

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install --global typescript@7.0.2 \
    && groupadd --system app && useradd --system --gid app --home-dir /app app \
    && mkdir -p /app /data/cache /data/catalog /data/runs \
    && chown -R app:app /app /data

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DETERMINISTIC_DATA_DIR=/data

USER app
ENTRYPOINT ["deterministic"]
CMD ["--help"]
