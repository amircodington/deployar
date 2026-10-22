"""Dockerfiles: app vs database image, system libraries, port, dev servers left in CMD."""

import re
from typing import Any

from deployar.analysis.detectors.common import fact, join, warn

DB_IMAGES = {"postgres": "postgres", "postgis": "postgres", "mysql": "mysql", "mariadb": "mysql", "mongo": "mongodb",
             "redis": "redis"}  # fmt: skip
DEV_SERVERS = ("runserver", "next dev", "npm run dev", "pnpm dev", "flask run", "--reload")


def base_image(text: str) -> str:
    m = re.search(r"^\s*FROM\s+(\S+)", text, re.M | re.I)
    return m.group(1).lower() if m else ""


def database_image(text: str) -> str | None:
    image = base_image(text).split("/")[-1].split(":")[0]
    return next((kind for name, kind in DB_IMAGES.items() if image.startswith(name)), None)


def detect(files: dict[str, str], root: str) -> dict[str, Any] | None:
    path = join(root, "Dockerfile")
    if path not in files:
        return None
    text = files[path]
    out: dict[str, Any] = {"dockerfile": path, "warnings": []}
    if re.search(r"apt-get install|apk add", text):
        out["installs_system_packages"] = True
    if m := re.search(r"^\s*EXPOSE\s+(\d+)", text, re.M | re.I):
        out["port"] = fact(int(m.group(1)), f"{path}#EXPOSE")
    elif m := re.search(r"(?:0\.0\.0\.0:|--port[ =]|-p )(\d{2,5})", text):
        out["port"] = fact(int(m.group(1)), f"{path}#CMD")
    cmd = " ".join(re.findall(r"^\s*(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.M | re.I))
    if any(s in cmd for s in DEV_SERVERS):
        out["warnings"].append(
            warn(
                "dev_server_in_cmd",
                "Dockerfile سرور توسعه را اجرا می‌کند؛ برای لیارا باید gunicorn/next start باشد.",
                path,
            )
        )
    return out
