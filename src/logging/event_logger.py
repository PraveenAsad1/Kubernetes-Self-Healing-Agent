import os
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv

# Try to import supabase, fallback if not configured
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

load_dotenv()
logger = logging.getLogger(__name__)

class EventLogger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.client = None
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if SUPABASE_AVAILABLE and url and key:
            try:
                self.client = create_client(url, key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        else:
            logger.warning("Supabase credentials missing or package not installed. Events will only be logged locally.")

    def log_event(self, event_type: str, stage: str, status: str, message: str, metadata: dict = None):
        """
        Logs a structured event to Supabase.
        """
        if metadata is None:
            metadata = {}
            
        event_data = {
            "id": str(uuid.uuid4()),
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "stage": stage,
            "status": status,
            "message": message,
            "metadata": metadata
        }
        
        # Always log to stdout for the console
        logger.info(f"[{stage}] {event_type} ({status}): {message}")
        if metadata:
            logger.debug(f"Metadata: {metadata}")
            
        # Push to Supabase if configured
        if self.client:
            try:
                # Assuming table is named 'incident_events'
                self.client.table("incident_events").insert(event_data).execute()
            except Exception as e:
                logger.error(f"Failed to send event to Supabase: {e}")
