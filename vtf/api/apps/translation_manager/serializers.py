from __future__ import annotations

from rest_framework import serializers

from apps.translation_manager.models import (
    TARGET_LANGUAGE_CHOICES,
    TranslationEntry,
    TranslationSource,
)


class TranslationEntrySerializer(serializers.ModelSerializer):
    key = serializers.CharField(source="source.key", read_only=True)
    translatedAt = serializers.DateTimeField(source="translated_at", read_only=True)

    class Meta:
        model = TranslationEntry
        fields = [
            "key",
            "language",
            "translated_text",
            "status",
            "model_used",
            "translatedAt",
        ]


class TranslationSourceSerializer(serializers.ModelSerializer):
    translations = TranslationEntrySerializer(many=True, read_only=True)

    class Meta:
        model = TranslationSource
        fields = [
            "key",
            "source_language",
            "source_text",
            "is_active",
            "translations",
        ]


class TranslationTriggerRequestSerializer(serializers.Serializer):
    key = serializers.SlugField(
        required=False,
        allow_blank=True,
        help_text="Optional TranslationSource key. Omit to sweep all pending/stale entries.",
    )
    language = serializers.ChoiceField(
        choices=[code for code, _ in TARGET_LANGUAGE_CHOICES] + [""],
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "Optional target language filter. Omit or blank to translate "
            "into every configured target language. Combine with `key` to translate "
            "one source into just this language, or omit `key` to sweep every "
            "pending/stale entry targeting this language."
        ),
    )


class TranslationTriggerResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    message = serializers.CharField()


class TranslationSourceSyncRequestSerializer(serializers.Serializer):
    translate = serializers.BooleanField(
        required=False,
        default=False,
        help_text="When true, queue pending/stale translations after syncing catalog sources.",
    )


class TranslationSourceSyncResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    message = serializers.CharField()
    translate = serializers.BooleanField()
    language = serializers.CharField()
