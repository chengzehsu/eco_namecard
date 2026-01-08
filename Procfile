web: gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 --access-logfile - --error-logfile - app:application
worker: python -m src.namecard.infrastructure.storage.rq_worker
