# Generated for apps.translation_manager

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="TranslationSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=160, unique=True)),
                ("source_language", models.CharField(choices=[("FR", "French")], default="FR", max_length=2)),
                ("source_text", models.TextField()),
                ("content_hash", models.CharField(blank=True, default="", editable=False, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["key"],
            },
        ),
        migrations.CreateModel(
            name="TranslationEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(choices=[("GB", "English")], max_length=2)),
                ("translated_text", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("translated", "Translated"), ("failed", "Failed")],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("model_used", models.CharField(blank=True, default="", max_length=120)),
                ("source_content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("error", models.TextField(blank=True, default="")),
                ("translated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translations",
                        to="translation_manager.translationsource",
                    ),
                ),
            ],
            options={
                "ordering": ["source__key", "language"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="translationentry",
            unique_together={("source", "language")},
        ),
    ]
