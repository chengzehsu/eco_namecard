"""
SocketIO Events for Drive Sync Progress

Provides real-time progress updates for Google Drive sync operations.
"""

from flask_socketio import SocketIO, emit, join_room, leave_room
import structlog

logger = structlog.get_logger()

# SocketIO instance - will be initialized in app.py
socketio: SocketIO = None


def init_socketio(app, **kwargs):
    """Initialize SocketIO with the Flask app."""
    global socketio
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",  # Use threading for compatibility
        **kwargs
    )
    register_events()
    logger.info("SocketIO initialized", async_mode="threading")
    return socketio


def get_socketio() -> SocketIO:
    """Get the SocketIO instance."""
    return socketio


def register_events():
    """Register SocketIO event handlers."""
    
    @socketio.on("connect")
    def handle_connect():
        logger.debug("SocketIO client connected")
    
    @socketio.on("disconnect")
    def handle_disconnect():
        logger.debug("SocketIO client disconnected")
    
    @socketio.on("join_sync_room")
    def handle_join_sync_room(data):
        """Join a tenant's sync progress room."""
        tenant_id = data.get("tenant_id")
        if tenant_id:
            room = f"sync_{tenant_id}"
            join_room(room)
            logger.debug("Client joined sync room", room=room)
            emit("room_joined", {"room": room, "tenant_id": tenant_id})
    
    @socketio.on("leave_sync_room")
    def handle_leave_sync_room(data):
        """Leave a tenant's sync progress room."""
        tenant_id = data.get("tenant_id")
        if tenant_id:
            room = f"sync_{tenant_id}"
            leave_room(room)
            logger.debug("Client left sync room", room=room)


def emit_sync_progress(tenant_id: str, progress: dict):
    """
    Emit sync progress to all clients in the tenant's room.
    
    Args:
        tenant_id: The tenant ID
        progress: Progress data dict with keys like:
            - status: 'processing', 'completed', 'failed', 'cancelled'
            - total_files: Total number of files
            - processed_files: Number processed so far
            - success_count: Successfully processed
            - error_count: Errors encountered
            - progress_percent: Completion percentage
            - current_file: Currently processing file name
    """
    if socketio is None:
        return
    
    room = f"sync_{tenant_id}"
    socketio.emit("sync_progress", progress, room=room)
    
    logger.debug(
        "Emitted sync progress",
        tenant_id=tenant_id,
        status=progress.get("status"),
        progress=progress.get("progress_percent"),
    )


def emit_sync_completed(tenant_id: str, result: dict):
    """
    Emit sync completion event.
    
    Args:
        tenant_id: The tenant ID
        result: Final result dict
    """
    if socketio is None:
        return
    
    room = f"sync_{tenant_id}"
    socketio.emit("sync_completed", result, room=room)
    
    logger.info(
        "Emitted sync completion",
        tenant_id=tenant_id,
        status=result.get("status"),
        success=result.get("success_count"),
    )
