"""POST /api/v1/mailer/send-simulation

Accepts the full simulation payload, renders the VTF HTML email, and
dispatches it through Brevo. Returns 200 on success, 400 on bad input,
502 on Brevo error.
"""
from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from apps.mailer.brevo_client import BrevoError, send_transactional_email
from apps.mailer.email_builder import build_html, build_subject
from apps.mailer.serializers import SendSimulationSerializer
from common.response import CustomResponse

logger = logging.getLogger(__name__)


class SendSimulationEmailView(APIView):
    """Send the VTF budget simulation as a branded HTML email via Brevo."""

    @extend_schema(
        request=SendSimulationSerializer,
        responses={
            200: {"description": "Email sent successfully.", "example": {"messageId": "<...>"}},
            400: {"description": "Validation error."},
            502: {"description": "Brevo API error."},
        },
        summary="Send simulation email",
        description=(
            "Renders the VTF vacation-budget simulation as a branded HTML email "
            "and sends it to the provided recipient via the Brevo transactional API."
        ),
        tags=["mailer"],
    )
    def post(self, request):
        ser = SendSimulationSerializer(data=request.data)
        
        if not ser.is_valid():
            error_detail = {}
            for field, errors in ser.errors.items():
                error_detail[field] = errors[0] if isinstance(errors, list) else str(errors)
            return CustomResponse.error(
                "Validation failed. Please check your input.",
                errors=error_detail,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        data = ser.validated_data
        logger.info("mailer_simulation_email_started recipient=%s", data["recipientEmail"])

        try:
            subject = build_subject(data)
            html = build_html(data)
        except Exception as e:
            logger.exception("Error building email content: %s", e)
            return CustomResponse.error(
                "Failed to build email content.",
                data={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            result = send_transactional_email(
                to_email=data["recipientEmail"],
                subject=subject,
                html_content=html,
                tags=["simulation", "vtf-budget"],
            )
            
        except BrevoError as exc:
            logger.warning("Brevo dispatch failed for %s: %s", data["recipientEmail"], exc)
            
            # Determine HTTP status based on Brevo error
            if exc.status_code == 401:
                http_status = status.HTTP_401_UNAUTHORIZED
            elif exc.status_code == 403:
                http_status = status.HTTP_403_FORBIDDEN
            elif exc.status_code == 429:
                http_status = status.HTTP_429_TOO_MANY_REQUESTS
            elif exc.status_code in [500, 503, 504]:
                http_status = status.HTTP_502_BAD_GATEWAY
            else:
                http_status = status.HTTP_502_BAD_GATEWAY
            
            return CustomResponse.error(
                "Email delivery failed.",
                data={
                    "detail": exc.detail,
                    "brevoStatusCode": exc.status_code,
                },
                status_code=http_status,
            )
            
        except Exception as exc:
            logger.exception("Unexpected error sending simulation email: %s", exc)
            return CustomResponse.error(
                "Unexpected error during email delivery.",
                data={"detail": str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "mailer_simulation_email_sent recipient=%s message_id=%s",
            data["recipientEmail"],
            result.get("messageId", ""),
        )
        return CustomResponse.success(
            "Simulation email sent successfully.",
            data={
                "messageId": result.get("messageId", ""),
                "recipient": data["recipientEmail"],
                "sentAt": timezone.now().isoformat(),
            },
        )
