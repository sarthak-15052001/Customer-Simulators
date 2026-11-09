"""Django admin for the translation table.

TranslationSource is the editable (French) row staff write.
TranslationEntry is read-only — it is always overwritten by the Celery task,
never hand-edited, so editing it in the admin would just be undone on the
next run.
"""
from __future__ import annotations

from django.contrib import admin, messages
from django.urls import reverse

from apps.translation_manager.models import TranslationEntry, TranslationSource


class TranslationEntryInline(admin.TabularInline):
    model = TranslationEntry
    extra = 0
    fields = ["language", "status", "translated_text", "model_used", "translated_at"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TranslationSource)
class TranslationSourceAdmin(admin.ModelAdmin):
    # Same client request as TranslationEntryAdmin below: the `key` column
    # (e.g. "catalog-activity-nom-1") doesn't say what content it is, so
    # staff couldn't tell what they were searching for from the list view.
    # search_fields already included source_text, but the change list never
    # displayed it — add a "Source word" column right after the key so staff
    # can see (and search) the actual source word, not just its slug.
    change_list_template = "admin/translation_manager/base_change_list.html"
    list_display = [
        "key",
        "source_word",
        "source_language",
        "source_model_ref",
        "is_active",
        "translation_status_summary",
        "updated_at",
    ]
    list_filter = ["source_language", "is_active"]
    search_fields = ["key", "source_text", "notes", "source_model_ref"]
    readonly_fields = ["content_hash", "source_model_ref", "created_at", "updated_at"]
    inlines = [TranslationEntryInline]
    actions = ["translate_now"]

    @admin.display(description="Source word", ordering="source_text")
    def source_word(self, obj: TranslationSource) -> str:
        text = obj.source_text or ""
        return (text[:80] + "…") if len(text) > 80 else text

    @admin.display(description="Translations")
    def translation_status_summary(self, obj: TranslationSource) -> str:
        entries = list(obj.translations.all())
        if not entries:
            return "—"
        return ", ".join(f"{e.language}:{e.status}" for e in entries)

    @admin.action(description="Translate selected sources now")
    def translate_now(self, request, queryset):
        from apps.translation_manager.tasks import task_translate_source

        queued = 0
        for source in queryset:
            task_translate_source.delay(source.pk)
            queued += 1
        messages.success(request, f"Queued translation for {queued} source(s).")

    def get_urls(self):
        urls = super().get_urls()
        from apps.translation_manager.admin_urls import urlpatterns as control_urls

        return control_urls + urls


@admin.register(TranslationEntry)
class TranslationEntryAdmin(admin.ModelAdmin):
    # Client request: staff couldn't search effectively by the `key` column
    # alone, since keys are opaque slugs (e.g. "catalog.village.description.
    # talloires") and don't say what content is actually being translated.
    # Searching/displaying by the *translated* word was ruled out too — it
    # would mean searching across every target language's translated text,
    # which the client noted is complex and slow for the database (it would
    # require OR-ing a LIKE query across N language columns/rows instead of
    # one canonical source column). The fix: search and display the
    # `source_word` (source.source_text) instead — the original word a user
    # sees on the site — so staff can look it up once and see every
    # language's translation for it.
    list_display = [
        "source",
        "source_word",
        "language",
        "status",
        "model_used",
        "is_stale",
        "translated_at",
    ]
    list_filter = ["language", "status"]
    search_fields = ["source__key", "source__source_text"]
    readonly_fields = [
        "source",
        "language",
        "translated_text",
        "status",
        "model_used",
        "source_content_hash",
        "error",
        "translated_at",
        "created_at",
        "updated_at",
    ]
    actions = ["retranslate"]

    def get_queryset(self, request):
        # search_fields above spans a related field (source__source_text),
        # so select_related keeps that from N+1-querying source_word/is_stale
        # for every row of the change list.
        return super().get_queryset(request).select_related("source")

    @admin.display(description="Source word", ordering="source__source_text")
    def source_word(self, obj: TranslationEntry) -> str:
        text = obj.source.source_text or ""
        return (text[:80] + "…") if len(text) > 80 else text

    @admin.display(boolean=True, description="Stale")
    def is_stale(self, obj: TranslationEntry) -> bool:
        return obj.is_stale

    @admin.action(description="Re-translate selected entries now")
    def retranslate(self, request, queryset):
        from apps.translation_manager.tasks import task_translate_source

        source_ids = sorted({entry.source_id for entry in queryset})
        for source_id in source_ids:
            task_translate_source.delay(source_id)
        messages.success(request, f"Queued re-translation for {len(source_ids)} source(s).")

    def has_add_permission(self, request) -> bool:
        return False
