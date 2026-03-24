from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from redis import Redis

_MEMORY_LOCK = Lock()
_MEMORY_CONNECTION_COUNTS: dict[tuple[int, int], int] = defaultdict(int)
_MEMORY_ONLINE_USERS: dict[int, set[int]] = defaultdict(set)
_MEMORY_LAST_SEEN: dict[tuple[int, int], timezone.datetime] = {}


@dataclass
class PresenceUpdate:
    became_online: bool = False
    became_offline: bool = False
    last_seen_at: timezone.datetime | None = None


class RoomPresenceService:
    @classmethod
    def mark_connected(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        if cls._use_memory_backend():
            return cls._mark_connected_memory(room_id=room_id, user_id=user_id)
        return cls._mark_connected_redis(room_id=room_id, user_id=user_id)

    @classmethod
    def mark_disconnected(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        if cls._use_memory_backend():
            return cls._mark_disconnected_memory(room_id=room_id, user_id=user_id)
        return cls._mark_disconnected_redis(room_id=room_id, user_id=user_id)

    @classmethod
    def online_user_ids(cls, *, room_id: int) -> set[int]:
        if cls._use_memory_backend():
            with _MEMORY_LOCK:
                return set(_MEMORY_ONLINE_USERS.get(room_id, set()))
        redis_client = cls._redis_client()
        return {int(value) for value in redis_client.smembers(cls._online_users_key(room_id))}

    @classmethod
    def last_seen_map(cls, *, room_id: int) -> dict[int, timezone.datetime]:
        if cls._use_memory_backend():
            with _MEMORY_LOCK:
                return {
                    user_id: seen_at
                    for (seen_room_id, user_id), seen_at in _MEMORY_LAST_SEEN.items()
                    if seen_room_id == room_id
                }
        redis_client = cls._redis_client()
        raw_map = redis_client.hgetall(cls._last_seen_key(room_id))
        return {
            int(user_id.decode() if isinstance(user_id, bytes) else user_id): parse_datetime(
                value.decode() if isinstance(value, bytes) else value
            )
            for user_id, value in raw_map.items()
        }

    @classmethod
    def presence_map(cls, *, room_id: int) -> dict[int, dict]:
        online_user_ids = cls.online_user_ids(room_id=room_id)
        last_seen_map = cls.last_seen_map(room_id=room_id)
        all_user_ids = online_user_ids | set(last_seen_map.keys())
        return {
            user_id: {
                "is_online": user_id in online_user_ids,
                "last_seen_at": last_seen_map.get(user_id),
            }
            for user_id in all_user_ids
        }

    @staticmethod
    def _use_memory_backend() -> bool:
        configured = getattr(settings, "PRESENCE_BACKEND", "auto")
        if configured == "memory":
            return True
        if configured == "redis":
            return False
        backend = settings.CHANNEL_LAYERS["default"]["BACKEND"]
        return backend == "channels.layers.InMemoryChannelLayer"

    @staticmethod
    def _redis_client() -> Redis:
        return Redis.from_url(settings.REDIS_URL, decode_responses=False)

    @staticmethod
    def _connections_key(room_id: int, user_id: int) -> str:
        return f"walkie:presence:room:{room_id}:user:{user_id}:connections"

    @staticmethod
    def _online_users_key(room_id: int) -> str:
        return f"walkie:presence:room:{room_id}:online_users"

    @staticmethod
    def _last_seen_key(room_id: int) -> str:
        return f"walkie:presence:room:{room_id}:last_seen"

    @classmethod
    def _mark_connected_memory(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        now = timezone.now()
        with _MEMORY_LOCK:
            key = (room_id, user_id)
            _MEMORY_CONNECTION_COUNTS[key] += 1
            became_online = _MEMORY_CONNECTION_COUNTS[key] == 1
            _MEMORY_ONLINE_USERS[room_id].add(user_id)
            _MEMORY_LAST_SEEN[key] = now
        return PresenceUpdate(became_online=became_online, last_seen_at=now)

    @classmethod
    def _mark_disconnected_memory(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        now = timezone.now()
        with _MEMORY_LOCK:
            key = (room_id, user_id)
            count = _MEMORY_CONNECTION_COUNTS.get(key, 0)
            if count <= 1:
                _MEMORY_CONNECTION_COUNTS.pop(key, None)
                room_users = _MEMORY_ONLINE_USERS.get(room_id)
                if room_users is not None:
                    room_users.discard(user_id)
                _MEMORY_LAST_SEEN[key] = now
                return PresenceUpdate(became_offline=True, last_seen_at=now)
            _MEMORY_CONNECTION_COUNTS[key] = count - 1
            _MEMORY_LAST_SEEN[key] = now
            return PresenceUpdate(last_seen_at=now)

    @classmethod
    def _mark_connected_redis(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        redis_client = cls._redis_client()
        now = timezone.now()
        count = redis_client.incr(cls._connections_key(room_id, user_id))
        redis_client.sadd(cls._online_users_key(room_id), user_id)
        redis_client.hset(cls._last_seen_key(room_id), user_id, now.isoformat())
        return PresenceUpdate(became_online=count == 1, last_seen_at=now)

    @classmethod
    def _mark_disconnected_redis(cls, *, room_id: int, user_id: int) -> PresenceUpdate:
        redis_client = cls._redis_client()
        now = timezone.now()
        key = cls._connections_key(room_id, user_id)
        remaining = redis_client.decr(key)
        redis_client.hset(cls._last_seen_key(room_id), user_id, now.isoformat())
        if remaining <= 0:
            redis_client.delete(key)
            redis_client.srem(cls._online_users_key(room_id), user_id)
            return PresenceUpdate(became_offline=True, last_seen_at=now)
        return PresenceUpdate(last_seen_at=now)
