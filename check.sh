#!/bin/sh -ex
uv run ruff check -q
uv run pytest -q --color=no
