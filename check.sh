#!/bin/sh -ex
uv run ruff format --check
uv run ruff check -q
uv run mypy splain/
uv run pytest -q --color=no
