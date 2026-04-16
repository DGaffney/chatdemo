FROM node:24-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

WORKDIR /app

# System libs required by opencv-python (pulled in by docling's table-structure
# model). Without these, `import cv2` fails with "libxcb.so.1: cannot open
# shared object file" on the slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir ".[documents]"

COPY .env.example ./.env.example
COPY --from=frontend-build /app/frontend/dist ./backend/static
COPY docs/ ./docs/

RUN mkdir -p /app/data /app/docs

ENV DATABASE_PATH=/app/data/frontdesk.db
ENV HANDBOOK_PATH=/app/backend/handbook
ENV DOCUMENTS_PATH=/app/docs

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
