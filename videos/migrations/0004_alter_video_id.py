# Generated by Django 4.1.7 on 2023-04-09 17:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0003_alter_video_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="video",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
