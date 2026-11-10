from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel


class StoredResult(BaseModel):
    result_id: str
    created_at: datetime
    payload: dict


_RESULTS: dict[str, StoredResult] = {}


def store_result(payload: dict) -> StoredResult:
    result = StoredResult(
        result_id=f"res-{uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        payload=payload,
    )
    _RESULTS[result.result_id] = result
    return result


def get_result(result_id: str) -> StoredResult | None:
    return _RESULTS.get(result_id)


def list_results(limit: int = 20) -> list[StoredResult]:
    return list(reversed(list(_RESULTS.values())))[:limit]
