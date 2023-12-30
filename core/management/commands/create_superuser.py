# myapp/management/commands/create_superuser.py
from django.core.management.base import BaseCommand
from core.models import CustomUser  # Import your custom user model

class Command(BaseCommand):
    help = 'Create a superuser'

    def handle(self, *args, **options):
        if not CustomUser.objects.filter(username='oscar').exists():
            CustomUser.objects.create_superuser('oscar', 'oscar@example.com', 'adminpassword')
            self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
        else:
            self.stdout.write(self.style.SUCCESS('Superuser already exists'))
