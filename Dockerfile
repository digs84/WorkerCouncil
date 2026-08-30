# Container for the shared hosted backend (the one place the free-tier
# API keys live). Deploy this to any Docker-friendly host - Render's free
# tier is documented in README.md, but this image is portable to any
# platform that runs a Dockerfile and gives you a PORT env var.

FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# On container start: (re)download each configured law's text (the
# filesystem is ephemeral on most free hosts, so this runs fresh each boot
# rather than relying on a build-time step), then start the server. Each
# fetch is independent - if one fails (e.g. transient network hiccup or a
# site schema change), the app still starts and still answers using
# whichever law(s) did load, instead of crash-looping the whole service.
CMD sh -c "python scripts/fetch_betrvg.py || echo 'WARNING: could not fetch BetrVG text at startup - see scripts/fetch_betrvg.py output above'; python scripts/fetch_bdsg.py || echo 'WARNING: could not fetch BDSG text at startup - see scripts/fetch_bdsg.py output above'; uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"
