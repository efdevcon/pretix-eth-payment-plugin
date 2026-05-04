"""Celery tasks for periodic cleanup."""
from pretix.celery_app import app
from pretix_eth.x402 import ticketstore


@app.task
def cleanup_expired_pending_task():
    deleted = ticketstore.cleanup_expired_pending()
    return {'deleted': deleted}


@app.task
def cleanup_verify_attempts_task():
    deleted = ticketstore.cleanup_verify_attempts()
    return {'deleted': deleted}
