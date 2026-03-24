from django.contrib.auth import login

from users.models import User


class UserService:
    @staticmethod
    def demo_login(request, *, display_name: str, email: str | None, preferred_output_language: str):
        if email:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": display_name,
                    "preferred_output_language": preferred_output_language,
                },
            )
            user.display_name = display_name
            user.preferred_output_language = preferred_output_language
            user.save(update_fields=["display_name", "preferred_output_language", "updated_at"])
        else:
            user = User.objects.create(
                display_name=display_name,
                preferred_output_language=preferred_output_language,
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return user
