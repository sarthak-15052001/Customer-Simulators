from __future__ import annotations

from rest_framework import serializers


class LogEntrySerializer(serializers.Serializer):
    timestamp = serializers.CharField(allow_blank=True)
    level = serializers.CharField(allow_blank=True)
    logger = serializers.CharField(allow_blank=True)
    message = serializers.CharField(allow_blank=True)
    process = serializers.CharField(allow_blank=True, required=False)
    thread = serializers.CharField(allow_blank=True, required=False)
    details = serializers.DictField(required=False)


class PaginatedLogSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    limit = serializers.IntegerField()
    totalPages = serializers.IntegerField()
    nextPage = serializers.IntegerField(allow_null=True)
    previousPage = serializers.IntegerField(allow_null=True)
    results = LogEntrySerializer(many=True)
