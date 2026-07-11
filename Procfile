web: gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --worker-class gthread --threads 4 --timeout 120 --access-logfile - --error-logfile - app:application
worker: python -m src.namecard.infrastructure.storage.rq_worker
