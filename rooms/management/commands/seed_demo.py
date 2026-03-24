from django.core.management.base import BaseCommand

from rooms.models import Room, RoomParticipant
from rooms.services import RoomService
from users.models import User


class Command(BaseCommand):
    help = "Create demo users, a demo room, and memberships for local development."

    def handle(self, *args, **options):
        demo_users = [
            {"email": "aman@example.com", "display_name": "Aman", "preferred_output_language": "en"},
            {"email": "sofia@example.com", "display_name": "Sofia", "preferred_output_language": "hi"},
            {"email": "marc@example.com", "display_name": "Marc", "preferred_output_language": "ta"},
        ]
        users = []
        for payload in demo_users:
            user, _ = User.objects.get_or_create(
                email=payload["email"],
                defaults={
                    "display_name": payload["display_name"],
                    "preferred_output_language": payload["preferred_output_language"],
                },
            )
            users.append(user)

        room = Room.objects.filter(name="Walkie Demo Room").first()
        if not room:
            room = RoomService.create_room(
                creator=users[0], name="Walkie Demo Room", is_private=False
            )

        for user in users[1:]:
            RoomParticipant.objects.get_or_create(room=room, user=user)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users and room '{room.name}' (code: {room.code})."
            )
        )
