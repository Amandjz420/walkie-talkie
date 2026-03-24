from rest_framework import authentication, exceptions

from users.models import User


class DemoHeaderAuthentication(authentication.BaseAuthentication):
    """
    Lightweight auth for MVP frontend integration.
    Send X-Demo-User-Id: <id> with API requests when not using sessions.
    """

    header_name = "HTTP_X_DEMO_USER_ID"

    def authenticate(self, request):
        user_id = request.META.get(self.header_name)
        if not user_id:
            return None
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid demo user id.") from exc
        return (user, None)
