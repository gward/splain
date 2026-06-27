# splain - find stock price moves and correlated news stories

## Setup

You need to install uv first, e.g.
```
brew install uv
```

Then you can setup a virtualenv for this project:
```
uv sync
```

## Automated tests

Run all tests and linters:

```
./check.sh
```

## Try it out

Command-line interface: look foor price moves of at least 5% in GOOG, from May 15 to Jun 20 2026.
Search for news stories +/- 1 day from each price move and list everything:

```
uv run splain GOOG --from 2026-05-15 --to 2026-06-20 --threshold 5.0 --window 1
```

Web interface: start the API server with

```
uv run splain --api
```

and then you can do the same query as above as follows:
```
curl "http://localhost:5000/correlatiojns/GOOG?from=2026-05-15&to=2026-06-20&threshold=5.0&window=1.0"
```
