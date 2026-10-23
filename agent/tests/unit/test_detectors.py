"""Repo analyzer: deterministic detectors over a repo's manifests (B-09). Every fact names its file."""

import json

from repo_fixtures import TOROB_GARD

from deployar.analysis.analyze import Repo, analyze


def app(result: dict, root: str) -> dict:
    return next(a for a in result["apps"] if a["root"] == root)


def test_torob_gard_is_two_apps_with_postgis_postgres() -> None:
    r = analyze(Repo.from_files(TOROB_GARD))
    assert sorted(a["root"] for a in r["apps"]) == ["api", "web"]  # deploy/db is a database image, not an app

    api = app(r, "api")
    assert api["platform"]["value"] == "docker"  # GDAL needs system libraries
    assert api["platform"]["source"] == "api/Dockerfile"
    assert api["framework"]["name"] == "django"
    assert api["runtime"] == {"name": "python", "version": "3.13", "source": "api/pyproject.toml#requires-python"}
    assert api["port"]["value"] == 8000
    assert {w["code"] for w in api["warnings"]} >= {"dev_server_in_cmd", "debug_default_on"}

    web = app(r, "web")
    assert web["platform"] == {"value": "next", "source": "web/package.json#dependencies.next"}
    assert web["package_manager"] == "pnpm" and web["build_cmd"] == "pnpm build"

    db = r["database"]
    assert db["kind"] == "postgres"
    assert set(db["extensions"]) == {"postgis", "pgvector"}
    assert "api/torobgard/settings.py" in " ".join(db["evidence"])
    assert r["cache"]["kind"] == "redis"

    env = {e["key"]: e for e in r["env_vars"]}
    assert env["DATABASE_URL"]["fill"] == "from_created_db" and env["DATABASE_URL"]["secret"]
    assert env["DJANGO_SECRET_KEY"]["fill"] == "generate"
    assert env["BOXAPI_KEY"]["secret"] and env["BOXAPI_KEY"]["fill"] == "ask_user"
    assert env["DATASET_DIR"]["source"] == ".env.example:5"


def test_next_with_prisma_postgres() -> None:
    files = {
        "package.json": json.dumps(
            {
                "scripts": {"build": "next build", "start": "next start -p 4000"},
                "dependencies": {"next": "15.1.0", "@prisma/client": "6"},
                "engines": {"node": ">=20"},
            }
        ),  # fmt: skip
        "package-lock.json": "{}",
        ".nvmrc": "22\n",
        "prisma/schema.prisma": 'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n',
    }
    r = analyze(Repo.from_files(files))
    a = r["apps"][0]
    assert a["root"] == "." and a["platform"]["value"] == "next"
    assert a["runtime"] == {"name": "node", "version": "22", "source": ".nvmrc"}
    assert a["package_manager"] == "npm" and a["port"]["value"] == 4000
    assert r["database"]["kind"] == "postgres" and r["database"]["orm"] == "prisma"
    assert "prisma/schema.prisma" in r["database"]["evidence"][0]


def test_express_with_mongo() -> None:
    pkg = {"scripts": {"start": "node server.js"}, "dependencies": {"express": "4", "mongoose": "8"}}
    files = {"package.json": json.dumps(pkg), "yarn.lock": ""}
    r = analyze(Repo.from_files(files))
    assert r["apps"][0]["platform"]["value"] == "node" and r["apps"][0]["package_manager"] == "yarn"
    assert r["database"]["kind"] == "mongodb"


def test_static_and_laravel_and_custom_docker() -> None:
    assert analyze(Repo.from_files({"index.html": "<html></html>"}))["apps"][0]["platform"]["value"] == "static"
    laravel = analyze(Repo.from_files({"composer.json": json.dumps({"require": {"laravel/framework": "^11"}}),
                                       ".env.example": "DB_CONNECTION=mysql\nAPP_KEY=\n"}))  # fmt: skip
    assert laravel["apps"][0]["platform"]["value"] == "laravel"
    assert laravel["database"]["kind"] == "mysql"
    docker = analyze(Repo.from_files({"Dockerfile": 'FROM golang:1.23\nEXPOSE 9090\nCMD ["/app"]\n'}))
    assert docker["apps"][0]["platform"]["value"] == "docker" and docker["apps"][0]["port"]["value"] == 9090


def test_nothing_deployable_is_a_warning_not_a_guess() -> None:
    r = analyze(Repo.from_files({"README.md": "hello"}))
    assert r["apps"] == [] and r["warnings"][0]["code"] == "no_app_found"


def test_a_root_dockerfile_that_builds_the_sub_apps_is_one_app() -> None:
    files = {
        "web/package.json": json.dumps({"dependencies": {"next": "16"}}),
        "agent/pyproject.toml": "[project]\n",
        "Dockerfile": "FROM node:24 AS web\nCOPY web/ ./\nFROM python:3.13\nCOPY agent/ ./\nEXPOSE 3000\n",
    }
    assert [a["root"] for a in analyze(Repo.from_files(files))["apps"]] == ["."]
    files["Dockerfile"] = "FROM ghcr.io/me/app:latest\nEXPOSE 3000\n"  # pulls the image CI built from them
    assert [a["root"] for a in analyze(Repo.from_files(files))["apps"]] == ["."]
    files["Dockerfile"] = "FROM python:3.13\nCOPY . .\n"  # a local-dev image: the sub-apps stay separate
    assert [a["root"] for a in analyze(Repo.from_files(files))["apps"]] == ["agent", "web"]
