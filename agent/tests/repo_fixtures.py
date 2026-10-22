"""Repo fixtures for the analyzer: the manifests of real projects (no code, no data)."""

import json

TOROB_GARD = {
    "api/pyproject.toml": """[project]
name = "torobgard-api"
requires-python = ">=3.13"
dependencies = ["django>=5.2,<5.3", "django-ninja", "psycopg[binary]", "redis"]
""",
    "api/manage.py": "import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', 'torobgard.settings')\n",
    "api/torobgard/settings.py": """DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.gis", "catalog"]
DATABASES = {"default": {"ENGINE": "django.contrib.gis.db.backends.postgis"}}
""",
    "api/Dockerfile": """FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin libgdal-dev libgeos-dev libproj-dev
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
CMD python manage.py runserver 0.0.0.0:8000
""",
    "api/uv.lock": "",
    "deploy/db/Dockerfile": "FROM imresamu/postgis:16-3.5\nRUN apt-get install -y postgresql-16-pgvector\n",
    "web/package.json": json.dumps(
        {
            "name": "web",
            "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
            "dependencies": {"next": "16.4.2", "react": "19.3.0"},
        }
    ),  # fmt: skip
    "web/pnpm-lock.yaml": "",
    "docker-compose.yml": "services:\n  db:\n    build: ./deploy/db\n  redis:\n    image: redis:7-alpine\n",
    ".env.example": "DATABASE_URL=postgresql://u:p@db:5432/x\nREDIS_URL=redis://redis:6379/0\nBOXAPI_KEY=\n"
    "DJANGO_SECRET_KEY=change-me\nDATASET_DIR=/data\n",
}
