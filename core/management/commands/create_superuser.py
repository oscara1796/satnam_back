# myapp/management/commands/create_superuser.py
from django.core.management.base import BaseCommand
from core.models import CustomUser  # Import your custom user model
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Create a superuser'

    def handle(self, *args, **options):
        if not CustomUser.objects.filter(username='oscar').exists():
            CustomUser.objects.create_superuser('oscar', 'oscar@example.com', 'adminpassword')
            self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
        else:
            self.stdout.write(self.style.SUCCESS('Superuser already exists'))


class Command(BaseCommand):
    help = 'Create a staff user'

    def handle(self, *args, **options):
        User = get_user_model()
        username = 'staffuser'  # Replace with desired username
        email = 'staff@example.com'  # Replace with desired email
        password = 'staffpassword'  # Replace with desired password

        if not User.objects.filter(username=username).exists():
            User.objects.create_user(username, email, password, is_staff=True)
            self.stdout.write(self.style.SUCCESS('Staff user created successfully'))
        else:
            self.stdout.write(self.style.SUCCESS('Staff user already exists'))