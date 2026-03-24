from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from users.models import User


@database_sync_to_async
def get_user_for_query_string(query_string: bytes):
    params = parse_qs(query_string.decode())
    user_id = (
        params.get("user_id", [None])[0]
        or params.get("userId", [None])[0]
        or params.get("demo_user_id", [None])[0]
        or params.get("demoUserId", [None])[0]
    )
    if not user_id:
        return AnonymousUser()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class QueryStringDemoAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("user") is None or scope["user"].is_anonymous:
            scope["user"] = await get_user_for_query_string(scope.get("query_string", b""))
        return await self.inner(scope, receive, send)
