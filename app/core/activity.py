import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


async def record_activity(
    db: AsyncIOMotorDatabase,
    actor: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> dict:
    """Ghi nhận nhật ký hoạt động hệ thống (F23 Audit Logging).
    Lưu vào MongoDB Atlas collection 'activity_logs'.
    """
    now = datetime.now(timezone.utc)
    entry = {
        "id": f"act-{uuid.uuid4().hex[:10]}",
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "timestamp": now,
    }
    await db["activity_logs"].insert_one(entry)
    return entry
