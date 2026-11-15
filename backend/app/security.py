"""Limitação de pedidos por IP, em memória e por processo.

Em produção com várias instâncias, substituir por armazenamento partilhado (ex.: Redis).
Não confiar em cabeçalhos X-Forwarded-For fornecidos directamente pelo cliente.
"""
import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self):
        self._events = {}
        self._lock = threading.Lock()

    def check(self, key, limit, window_seconds, now=None):
        now = time.monotonic() if now is None else now
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, math.ceil(window_seconds - (now - events[0])))
            events.append(now)
            if len(self._events) > 10000:
                stale = [k for k, values in self._events.items()
                         if not values or values[-1] <= cutoff]
                for stale_key in stale:
                    self._events.pop(stale_key, None)
            return 0

    def clear(self):
        with self._lock:
            self._events.clear()


rate_limiter = RateLimiter()


def enforce_rate_limit(request: Request, action: str, limit: int, window_seconds: int):
    host = request.client.host if request.client else "unknown"
    retry_after = rate_limiter.check((action, host), limit, window_seconds)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limit_exceeded",
                    "message": "Limite temporário de pedidos atingido. Aguarde e tente novamente.",
                    "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )
