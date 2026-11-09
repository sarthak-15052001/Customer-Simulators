# VTF Mailer Service

Transactional email service for VTF vacation-budget simulations. Sends branded HTML emails via Brevo (formerly Sendinblue).

## Architecture

The mailer service follows a clean separation of concerns:

```
views.py              → REST endpoint (POST /api/v1/mailer/send-simulation)
    ↓
email_builder.py      → Email content generation (subject + HTML)
    ↓
templates/            → Django template for HTML rendering
    ↓
brevo_client.py       → Brevo API integration (transactional sending)
```

## Components

### 1. **email_builder.py**
Contains two public functions:

- `build_subject(data: dict) → str`
  - Generates email subject line
  - Format: "Mon projet vacances VTF — {villageName} · {nuits} nuits · {total} €"

- `build_html(data: dict) → str`
  - Renders HTML email content using Django templates
  - Uses `templates/mailer/vacation_budget_email.html`
  - All dynamic values are formatted with French thousand separators (thin space `\u202f`)

**Helper functions:**
- `_fmt(value)` — Format numbers with French separators (e.g., `1234` → `1\u202f234`)
- `_date_fr(d)` — Convert ISO date to dd/mm/yyyy format
- `_formule_label(code)` — Map formula codes to French labels
- `_formule_inclus(code)` — Get formula inclusion text
- `_env_label(key)` — Map environment keys to labels (mer, montagne, etc.)
- `_transport_label(mode, km)` — Build transport description

### 2. **templates/mailer/vacation_budget_email.html**
Responsive HTML email template using Django template syntax.

**Template variables:**
- Basic info: `villageName`, `nuits`, `saison`, `adultes`, `nb_enfants`
- Dates: `date_debut_str`, `date_fin_str`
- Labels: `formule_label`, `formule_inclus`, `env_label`, `transport_label`
- Formatted values (with suffix `_fmt`): `total_fmt`, `perPerson_fmt`, `perAdultBase_fmt`, etc.
- Conditionals: `activitiesTotal`, `restoTotal`, `transportTotal`, `hotelSavings`
- Arrays: `child_amounts_with_ages` for dynamic child rows

### 3. **brevo_client.py**
Thin REST wrapper around Brevo's SMTP API.

```python
send_transactional_email(
    to_email: str,
    subject: str,
    html_content: str,
    sender_email: str | None = None,
    sender_name: str | None = None,
    tags: list[str] | None = None,
) → dict
```

**Configuration (Django settings):**
- `BREVO_API_KEY` — Required. API key for Brevo v3
- `BREVO_SENDER_EMAIL` — Default: `noreply@vtf-vacances.com`
- `BREVO_SENDER_NAME` — Default: `VTF Vacances`

**Raises:**
- `BrevoError` on HTTP errors (with status code + detail)
- Network exceptions propagate unchanged

### 4. **views.py**
DRF APIView for the `POST /api/v1/mailer/send-simulation` endpoint.

**Request body:** `SendSimulationSerializer`
**Response:** 
- **200**: `{ "messageId": "...", "recipient": "..." }`
- **400**: Validation error
- **502**: Brevo API error

## Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Django Settings

```python
# settings/production.py
BREVO_API_KEY = "xkeysib-..."
BREVO_SENDER_EMAIL = "noreply@vtf-vacances.com"
BREVO_SENDER_NAME = "VTF Vacances"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,  # Must be True for template discovery
        'OPTIONS': {...}
    }
]
```

### 3. Send Simulation Email

```bash
curl -X POST http://localhost:8000/api/v1/mailer/send-simulation \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "recipientEmail": "client@example.com",
  "locale": "FR",
  "bookingUrl": "https://www.vtf-vacances.com/booking/...",
  "villageName": "Biarritz",
  "nuits": 7,
  "saison": "ete",
  "dateDebut": "2026-07-12",
  "dateFin": "2026-07-19",
  "adultes": 2,
  "enfantsAges": [8, 5],
  "formule": "PC",
  "envKey": "mer",
  "perPersonPerDay": 86,
  "perDayFamily": 612,
  "total": 4280,
  "perPerson": 1070,
  "perAdultBase": 595,
  "totalAdults": 1190,
  "childAmounts": [420, 420],
  "totalChildren": 840,
  "adhesion": 44,
  "staySubtotal": 2074,
  "activitiesTotal": 320,
  "restoTotal": 180,
  "transportMode": "car",
  "transportKm": 400,
  "transportTotal": 245,
  "hotelEstimate": 5890,
  "hotelSavings": 1610,
  "savingsPct": 27
}
EOF
```

### 4. Python Usage

```python
from apps.mailer.email_builder import build_html, build_subject
from apps.mailer.brevo_client import send_transactional_email

data = {
    "recipientEmail": "client@example.com",
    "villageName": "Biarritz",
    "nuits": 7,
    # ... other fields
}

subject = build_subject(data)
html = build_html(data)

result = send_transactional_email(
    to_email=data["recipientEmail"],
    subject=subject,
    html_content=html,
    tags=["simulation", "vtf-budget"]
)

print(result["messageId"])  # Brevo message ID
```

## Data Flow

1. Client sends POST request with simulation payload
2. `SendSimulationSerializer` validates all fields
3. `build_subject()` generates email subject
4. `build_html()` prepares template context and renders HTML
5. `send_transactional_email()` POSTs to Brevo SMTP API
6. Response with `messageId` returned to client

## Email Template Features

- **Responsive design**: Works on desktop, mobile, and webmail clients
- **French localization**: Dates, numbers, text all in French
- **Conditional sections**: Activities, restaurants, transport only show if populated
- **Color scheme**: VTF brand colors (navy #00445a, coral #f2a680)
- **Inline CSS**: All styles embedded for email compatibility
- **Accessibility**: Semantic HTML, alt text for logo

## Testing

### Unit Test Example

```python
from apps.mailer.email_builder import build_html, build_subject

def test_email_builder():
    data = {
        "recipientEmail": "test@example.com",
        "villageName": "Biarritz",
        "nuits": 7,
        "adultes": 2,
        "enfantsAges": [8, 5],
        "formule": "PC",
        "envKey": "mer",
        "perPersonPerDay": 86,
        "perDayFamily": 612,
        "total": 4280,
        # ... other fields
    }
    
    subject = build_subject(data)
    assert "Biarritz" in subject
    assert "4 280 €" in subject  # French formatting
    
    html = build_html(data)
    assert "<html" in html
    assert "4\u202f280" in html  # Thin-space formatted number
    assert "Pension complète" in html
```

### Integration Test with Brevo (Mocked)

```python
from unittest.mock import patch
from apps.mailer.views import SendSimulationEmailView

@patch("apps.mailer.brevo_client.requests.post")
def test_send_simulation_email(mock_post):
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {"messageId": "abc123"}
    
    view = SendSimulationEmailView.as_view()
    response = view(request_with_valid_payload)
    
    assert response.status_code == 200
    assert response.data["messageId"] == "abc123"
```

## Troubleshooting

### TemplateDoesNotExist Error
- Ensure `APP_DIRS=True` in Django settings
- Check `apps.mailer` is in `INSTALLED_APPS`
- Verify template path: `apps/mailer/templates/mailer/vacation_budget_email.html`

### Brevo API Error (502)
- Check `BREVO_API_KEY` is set and valid
- Test API key: `curl -H "api-key: YOUR_KEY" https://api.brevo.com/v3/account`
- Check API rate limits and IP allowlist settings

### Email Not Received
- Verify recipient email in the request payload
- Check Brevo campaign/statistics dashboard
- Look for bounces or unsubscribes
- Verify sender email is authorized in Brevo

## Future Enhancements

- [ ] Email template versioning (A/B testing)
- [ ] Multilingual support (EN localization)
- [ ] Attachment support (PDF invoice, terms)
- [ ] Campaign tracking (UTM parameters in booking URL)
- [ ] Reply-to handling for customer service
- [ ] Async task queue (Celery) for high-volume sending
