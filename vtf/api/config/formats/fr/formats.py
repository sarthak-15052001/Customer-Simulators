"""French date/number formats for the admin and any localized rendering.

Loaded through ``FORMAT_MODULE_PATH`` (see config/settings/base.py). Django
merges these over ``django.conf.locale.fr.formats``; anything left unset keeps
the stock French value.

Dates are pinned to the numeric ``JJ/MM/AAAA`` form used by the VTF booking
funnel ("7 nuits du 01/08/2026 au 08/08/2026") rather than the stock
long-form ``1 mars 2027``. Two reasons:

  * consistency — tariff bands are rendered from JSON, where dates are plain
    ISO strings with no model field to localize; formatting those long-form
    by hand would drift from whatever the locale does. One numeric format is
    reproducible on both paths (``admin_display.fr_date``).
  * density — season/band tables put date_start and date_end on every row,
    and long-form dates wrap.

``INPUT_FORMATS`` keep ISO first so existing admin forms, fixtures and API
payloads that post ``2026-08-01`` continue to validate.
"""

DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
YEAR_MONTH_FORMAT = "m/Y"
MONTH_DAY_FORMAT = "d/m"

DATE_INPUT_FORMATS = [
    "%Y-%m-%d",  # 2026-08-01 — ISO, what fixtures and the API send
    "%d/%m/%Y",  # 01/08/2026 — what staff type
    "%d/%m/%y",  # 01/08/26
]
DATETIME_INPUT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]
