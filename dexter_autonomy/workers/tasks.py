"""
Celery Tasks for Dexter Autonomy

Background tasks for:
- Email notifications (outbox processing)
- Scheduled observations (periodic OCR, monitoring)
- Agent mission execution (delegated by Dexter)
- Memory processing (embeddings, knowledge graph updates)
"""

import os
from celery import Celery

# Configure Celery
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "dexter_autonomy",
    broker=redis_url,
    backend=redis_url,
)

# Configure Celery settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(name="dexter_autonomy.workers.send_email")
def send_email(to: str, subject: str, body: str, html: bool = False):
    """
    Send email notification.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text or HTML)
        html: If True, body is HTML
    
    Returns:
        dict: {"status": "ok"|"error", "detail": "..."}
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    
    if not smtp_user or not smtp_password:
        return {
            "status": "error",
            "detail": "SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD env vars."
        }
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to
        
        mime_type = "html" if html else "plain"
        msg.attach(MIMEText(body, mime_type))
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        return {"status": "ok", "detail": f"Email sent to {to}"}
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@celery_app.task(name="dexter_autonomy.workers.process_observation")
def process_observation(agent_id: str, observation_type: str, data: dict):
    """
    Process scheduled observation (OCR, monitoring, etc.).
    
    Args:
        agent_id: Agent performing observation
        observation_type: Type of observation ("ocr", "monitor", etc.)
        data: Observation parameters
    
    Returns:
        dict: {"status": "ok"|"error", "result": {...}}
    """
    try:
        # Import here to avoid circular dependencies
        from dexter_autonomy.brain.enhanced_memory import EnhancedMemory
        
        # Store observation in memory
        memory = EnhancedMemory()
        memory_id = memory.add_memory(
            kind="scheduled_observation",
            content=f"Observation: {observation_type}",
            meta={
                "observation_type": observation_type,
                "data": data,
                "tags": ["observation", observation_type]
            },
            agent_id=agent_id
        )
        
        return {
            "status": "ok",
            "result": {
                "memory_id": memory_id,
                "observation_type": observation_type
            }
        }
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@celery_app.task(name="dexter_autonomy.workers.execute_mission")
def execute_mission(mission_id: str, agent_id: str, mission_data: dict):
    """
    Execute agent mission in background.
    
    Args:
        mission_id: Unique mission identifier
        agent_id: Agent executing mission
        mission_data: Mission parameters and steps
    
    Returns:
        dict: {"status": "ok"|"error", "result": {...}}
    """
    try:
        from dexter_autonomy.brain.enhanced_memory import EnhancedMemory
        
        # Store mission start
        memory = EnhancedMemory()
        memory.add_memory(
            kind="mission_start",
            content=f"Mission {mission_id} started",
            meta={
                "mission_id": mission_id,
                "mission_data": mission_data,
                "tags": ["mission", "start"]
            },
            agent_id=agent_id,
            task_root=mission_id
        )
        
        # TODO: Implement actual mission execution
        # This is a placeholder for future mission execution logic
        
        # Store mission completion
        memory.add_memory(
            kind="mission_complete",
            content=f"Mission {mission_id} completed",
            meta={
                "mission_id": mission_id,
                "tags": ["mission", "complete"]
            },
            agent_id=agent_id,
            task_root=mission_id
        )
        
        return {
            "status": "ok",
            "result": {
                "mission_id": mission_id,
                "completed": True
            }
        }
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@celery_app.task(name="dexter_autonomy.workers.update_embeddings")
def update_embeddings(memory_ids: list[int]):
    """
    Update embeddings for memory entries (background processing).
    
    Args:
        memory_ids: List of memory IDs to update
    
    Returns:
        dict: {"status": "ok"|"error", "updated": int}
    """
    try:
        from dexter_autonomy.brain.enhanced_memory import EnhancedMemory
        
        memory = EnhancedMemory()
        updated = 0
        
        for memory_id in memory_ids:
            # TODO: Implement actual embedding update
            # This is a placeholder for future embedding logic
            updated += 1
        
        return {
            "status": "ok",
            "updated": updated
        }
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@celery_app.task(name="dexter_autonomy.workers.cleanup_memory")
def cleanup_memory(max_stm_gb: float = 10.0):
    """
    Cleanup STM and move old memories to LTM.
    
    Args:
        max_stm_gb: Maximum STM size in GB
    
    Returns:
        dict: {"status": "ok"|"error", "evicted": int}
    """
    try:
        from dexter_autonomy.brain.enhanced_memory import EnhancedMemory
        
        memory = EnhancedMemory()
        
        # TODO: Implement STM eviction logic
        # This is a placeholder for future memory cleanup logic
        
        return {
            "status": "ok",
            "evicted": 0
        }
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Periodic tasks (Celery Beat schedule)
celery_app.conf.beat_schedule = {
    "cleanup-memory-hourly": {
        "task": "dexter_autonomy.workers.cleanup_memory",
        "schedule": 3600.0,  # Every hour
    },
}
