from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser or a staff user"

    def add_arguments(self, parser):
        # Adding a named (optional) argument
        parser.add_argument(
            "--staff",
            action="store_true",
            help="Create a staff user instead of a superuser",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        if options["staff"]:
            username = "staffuser"  # Replace with desired username
            email = "staff@example.com"  # Replace with desired email
            password = "staffpassword"  # Replace with desired password
            user_type = "Staff user"
            extra_fields = {"is_staff": True, "is_superuser": False}
        else:
            username = "oscar"
            email = "oscar@example.com"
            password = "adminpassword"
            user_type = "Superuser"
            extra_fields = {"is_staff": True, "is_superuser": True}

        if not User.objects.filter(username=username).exists():
            User.objects.create_user(username, email, password, **extra_fields)
            self.stdout.write(self.style.SUCCESS(f"{user_type} created successfully"))
        else:
            self.stdout.write(self.style.SUCCESS(f"{user_type} already exists"))
