# BinBooks

A trash can that does the books for everything thrown into it.

The product name lives in one file, `brand.json` at the repo root. The backend reads it at
startup and serves it at `GET /brand.json`, and the dashboard and phone page fetch it from
there. Nothing else in the repo writes the name down. Change `brand.json` and every surface
follows.

## Run the demo

```
scripts\demo_up.ps1
uv run --project backend python scripts/demo_up.py
```

One command starts the backend, the dashboard and the webcam, and keeps them up. Use the
second line if PowerShell refuses to run scripts. The launcher prints this laptop's address
and the three URLs: the dashboard on `http://localhost:3000`, the phone on
`https://<laptop>:8443/phone`, the bin on `ws://<laptop>:8000/ws/bin`. In that same
terminal, type `toss 150` to put a 150 g item on the scale and `quit` to stop everything.

## Install

You need `uv` for Python and `pnpm` for anything under `frontend` or `phone`.

```
uv python install 3.12
cd backend
uv sync
```

## Run the backend

One process serves HTTPS on `:8443` for the phone, which only gets camera access on a secure
origin, and plain HTTP on `:8000` for the dashboard. The certificate is written on first run.

```
uv run --project backend python scripts/make_cert.py
uv run --project backend python scripts/run_backend.py
```

Check it answered:

```
curl -k https://localhost:8443/api/health
curl http://localhost:8000/api/health
```

Simulator routes and the API docs are off unless `DEV_TOOLS` is set:

```
DEV_TOOLS=true uv run --project backend python scripts/run_backend.py
```

## Run the tests

```
cd backend
uv run pytest
uv run ruff check . ../scripts
uv run mypy
```

## Change a contract

`backend/app/schemas.py` is the single source for every wire message and every REST body.
After editing it, regenerate the files the dashboard and phone page read:

```
uv run --project backend python scripts/gen_types.py
```

`uv run pytest` fails if you forget. `firmware_contract.md` is the guide for the hardware
teammate and its examples are validated by the same suite, so it changes in the same commit as
the models.

## Run the dashboard and the phone page

Those live in `frontend` and `phone` and have their own README files.
