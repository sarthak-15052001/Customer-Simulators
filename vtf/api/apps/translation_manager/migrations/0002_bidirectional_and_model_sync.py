from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("translation_manager", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="translationsource",
            name="source_model_ref",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="translationsource",
            name="source_language",
            field=models.CharField(
                choices=[("FR", "French"), ("GB", "English")], default="FR", max_length=2
            ),
        ),
        migrations.AlterField(
            model_name="translationentry",
            name="language",
            field=models.CharField(choices=[("FR", "French"), ("GB", "English")], max_length=2),
        ),
    ]
