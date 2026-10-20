FROM python:3.13-slim

# Match these to the owner of the files you mount at /data (see `id -u` / `id -g`)
ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Unprivileged user with no login shell or home. The app code stays owned by
# root, so the running process cannot modify it; only /app/instance is writable.
RUN groupadd --gid "$GID" app \
 && useradd --uid "$UID" --gid "$GID" --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /app/instance && chown app:app /app/instance
COPY app ./app

# Numeric so runtimes can verify non-root (e.g. Kubernetes runAsNonRoot)
USER ${UID}:${GID}

EXPOSE 8000
# Threaded workers: sync workers are killed mid-stream after 30s, truncating large
# downloads, and two slow downloads would occupy every worker
CMD ["gunicorn", "-w", "2", "--worker-class", "gthread", "--threads", "8", "-b", "0.0.0.0:8000", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "app:create_app()"]
