"""Translation table API views.

Public:
  GET /api/v6/translations?lang=GB&key=some.key

Staff:
  POST /api/v6/admin/translation-manager/sync-sources
  POST /api/v6/admin/translation-manager/translate
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.translation_manager.models import TranslationEntry
from apps.translation_manager.serializers import (
    TranslationEntrySerializer,
    TranslationSourceSyncRequestSerializer,
    TranslationSourceSyncResponseSerializer,
    TranslationTriggerRequestSerializer,
    TranslationTriggerResponseSerializer,
)
from common.permissions import StaffAPIViewMixin
from common.response import CustomResponse

logger = logging.getLogger("translation_manager")

# Client request: cache this list for 7 days. Invalidation is handled by the
# post_save signal on TranslationEntry (see signals.py) so an admin edit /
# re-translation is never served stale for the full 7 days — the cache is a
# performance win for the common "unchanged" case, not a source of stale data.
TRANSLATION_LIST_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days, in seconds
TRANSLATION_LIST_CACHE_PREFIX = "vtf:translation-manager:list"


def _translation_list_cache_key(lang: str, key: str) -> str:
    return f"{TRANSLATION_LIST_CACHE_PREFIX}:lang={lang or 'ALL'}:key={key or 'ALL'}"


class TranslationListView(APIView):
    """Public read of translated entries from the admin translation table."""

    @extend_schema(
        parameters=[
            OpenApiParameter("lang", str, required=False, description="Target language, e.g. GB."),
            OpenApiParameter("key", str, required=False, description="Exact TranslationSource key."),
        ],
        responses={200: TranslationEntrySerializer(many=True)},
        tags=["v6"],
        summary="List translation table entries",
    )
    def get(self, request: Request) -> CustomResponse:
        lang = (request.query_params.get("lang") or "").strip().upper()
        key = (request.query_params.get("key") or "").strip()

        cache_key = _translation_list_cache_key(lang, key)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(
                "translation_list_cache_hit lang=%s key=%s", lang or "ALL", key or "ALL"
            )
            return CustomResponse.success(
                f"{len(cached)} translation(s) fetched.", data=cached
            )

        qs = TranslationEntry.objects.filter(
            status=TranslationEntry.STATUS_TRANSLATED, source__is_active=True
        ).select_related("source")

        if lang:
            qs = qs.filter(language=lang)

        if key:
            qs = qs.filter(source__key=key)

        data = TranslationEntrySerializer(qs, many=True).data
        cache.set(cache_key, data, TRANSLATION_LIST_CACHE_TTL)
        return CustomResponse.success(f"{len(data)} translation(s) fetched.", data=data)


class TranslationTriggerView(StaffAPIViewMixin, APIView):
    """Staff-only: queue a translation run for one source, or sweep all pending/stale."""

    serializer_class = TranslationTriggerRequestSerializer

    @extend_schema(
        request=TranslationTriggerRequestSerializer,
        responses={202: TranslationTriggerResponseSerializer},
        tags=["v6"],
        summary="Trigger translation run",
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = TranslationTriggerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = (serializer.validated_data.get("key") or "").strip()
        language = (serializer.validated_data.get("language") or "").strip().upper()
        language_label = f" → {language}" if language else ""

        if key:
            from apps.translation_manager.models import TranslationSource
            from apps.translation_manager.tasks import task_translate_source

            try:
                source = TranslationSource.objects.get(key=key)
            except TranslationSource.DoesNotExist:
                return CustomResponse.error(
                    f"No TranslationSource with key '{key}'.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            async_result = task_translate_source.delay(
                source.pk, [language] if language else None
            )
            message = f"Queued translation for '{key}'{language_label}."
        else:
            from apps.translation_manager.tasks import task_translate_pending

            async_result = task_translate_pending.delay(language=language or None)
            message = f"Queued sweep of pending/stale translations{language_label}."

        return CustomResponse.success(
            message,
            data={"task_id": async_result.id, "message": message},
            status_code=status.HTTP_202_ACCEPTED,
        )


class TranslationSourceSyncView(StaffAPIViewMixin, APIView):
    """Staff-only: sync catalog model fields into TranslationSource rows."""

    serializer_class = TranslationSourceSyncRequestSerializer

    @extend_schema(
        request=TranslationSourceSyncRequestSerializer,
        responses={202: TranslationSourceSyncResponseSerializer},
        tags=["v6"],
        summary="Sync catalog fields into translation sources",
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = TranslationSourceSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        should_translate = serializer.validated_data.get("translate", False)

        from apps.translation_manager.tasks import task_sync_translation_sources

        sync_result = task_sync_translation_sources.delay(should_translate, None)
        data = {
            "task_id": sync_result.id,
            "translate": should_translate,
            "language": "",
        }
        if should_translate:
            message = "Queued catalog source sync and pending translation sweep."
        else:
            message = "Queued catalog source sync."
        data["message"] = message

        return CustomResponse.success(
            message,
            data=data,
            status_code=status.HTTP_202_ACCEPTED,
        )
