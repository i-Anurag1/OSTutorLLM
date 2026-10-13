import hashlib
import json

import redis

from .config import settings


def _client():
    return redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)


def key(prefix, payload):
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return f"ostutor:{prefix}:{hashlib.sha256(raw).hexdigest()}"


def get_json(k):
    try:
        value = _client().get(k)
        return json.loads(value) if value else None
    except Exception:
        return None


def set_json(k, value, ttl=900):
    try:
        _client().setex(k, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def delete_prefix(prefix):
    try:
        r = _client()
        keys = list(r.scan_iter(match=f"ostutor:{prefix}:*"))
        if keys:
            r.delete(*keys)
    except Exception:
        pass
