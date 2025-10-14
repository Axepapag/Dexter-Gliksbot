"""
Dexter Autonomy Celery Workers

Background task processing for:
- Email notifications
- Scheduled observations
- Agent mission execution
- Memory processing
"""

from .tasks import celery_app

__all__ = ["celery_app"]
