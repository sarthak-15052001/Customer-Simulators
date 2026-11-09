# Mailer Service - Testing Guide

## Quick Start Testing

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Set Brevo API key
export BREVO_API_KEY="<your-brevo-api-key>"
```

### Test via Django Shell

```python
from apps.mailer.email_builder import build_html, build_subject

# Sample data
data = {
    "recipientEmail": "test@example.com",
    "locale": "FR",
    "bookingUrl": "https://www.vtf-vacances.com/booking/test",
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
    "savingsPct": 27,
}

# Test subject generation
subject = build_subject(data)
print(f"Subject: {subject}")
# Output: "Mon projet vacances VTF — Biarritz · 7 nuits · 4 280 €"

# Test HTML generation
html = build_html(data)
print(f"HTML length: {len(html)} chars")
print(f"Contains budget: {'4\u202f280' in html}")  # French format with thin space
print(f"Contains formule: {'Pension complète' in html}")
```

### Test via API (cURL)

```bash
# 1. Start Django development server
python manage.py runserver

# 2. Send test email
curl -X POST http://localhost:8000/api/v1/mailer/send-simulation \
  -H "Content-Type: application/json" \
  -d '{
    "recipientEmail": "your-email@example.com",
    "locale": "FR",
    "bookingUrl": "https://www.vtf-vacances.com/booking/demo",
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
  }'

# Expected response (200 OK):
# {
#   "success": true,
#   "message": "Simulation email sent.",
#   "data": {
#     "messageId": "abc123def456",
#     "recipient": "your-email@example.com"
#   }
# }
```

### Test via Python Requests

```python
import requests
import json

url = "http://localhost:8000/api/v1/mailer/send-simulation"

payload = {
    "recipientEmail": "test@example.com",
    "locale": "FR",
    "bookingUrl": "https://www.vtf-vacances.com/booking/test",
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

response = requests.post(url, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
```

### Test with Pytest

```python
# tests/test_mailer_email_builder.py
import pytest
from apps.mailer.email_builder import build_html, build_subject

@pytest.fixture
def sample_data():
    return {
        "recipientEmail": "client@example.com",
        "locale": "FR",
        "bookingUrl": "https://www.vtf-vacances.com/booking/test",
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
        "savingsPct": 27,
    }

def test_build_subject(sample_data):
    subject = build_subject(sample_data)
    assert "Biarritz" in subject
    assert "7 nuits" in subject
    assert "4 280 €" in subject  # French formatting

def test_build_html(sample_data):
    html = build_html(sample_data)
    
    # Check structure
    assert "<html" in html
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
    
    # Check content
    assert "Mon projet vacances" in html
    assert "Biarritz" in html
    assert "Pension complète" in html
    
    # Check French formatting (thin space)
    assert "4\u202f280" in html
    
    # Check family info
    assert "2 adultes" in html
    assert "2 enfants" in html
    assert "8 ans" in html
    assert "5 ans" in html
    
    # Check conditional sections (all present in sample data)
    assert "ACTIVITÉS" in html
    assert "RESTAURATION" in html
    assert "TRANSPORT" in html
    assert "Économies avec VTF" in html

def test_build_html_optional_sections():
    """Test that optional sections are hidden when values are zero"""
    data = {
        # ... required fields ...
        "activitiesTotal": 0,
        "restoTotal": 0,
        "transportTotal": 0,
        "hotelSavings": 0,
    }
    
    html = build_html(data)
    # These sections should not be fully rendered
    # (template uses {% if %} to conditionally show them)
    assert "ACTIVITÉS</p>" not in html or "Activités et options payantes (total)" not in html

def test_build_html_children_rendering():
    """Test child entries are properly rendered"""
    data = {
        # ... base data ...
        "enfantsAges": [3, 6, 10],
        "childAmounts": [150, 250, 350],
    }
    
    html = build_html(data)
    
    # Check all children appear
    assert "Enfant 1 (3 ans)" in html
    assert "Enfant 2 (6 ans)" in html
    assert "Enfant 3 (10 ans)" in html
    
    # Check formatted amounts
    assert "150 €" in html
    assert "250 €" in html
    assert "350 €" in html
```

### Run Tests

```bash
# Run all mailer tests
pytest apps/mailer/tests/ -v

# Run specific test
pytest apps/mailer/tests/test_email_builder.py::test_build_subject -v

# Run with coverage
pytest apps/mailer/tests/ --cov=apps.mailer --cov-report=html
```

## Manual Testing Checklist

- [ ] Email subject is generated correctly
- [ ] Email HTML renders without errors
- [ ] French number formatting (thin space) is applied
- [ ] Date formatting matches dd/mm/yyyy
- [ ] Budget breakdown is visible
- [ ] Optional sections (activities, transport) appear/hide correctly
- [ ] Child entries render dynamically
- [ ] Booking URL is clickable
- [ ] Email displays correctly in desktop client
- [ ] Email displays correctly on mobile
- [ ] Brevo API responds with messageId
- [ ] Email arrives in inbox (check spam folder)
- [ ] Links in email are clickable
- [ ] Footer/branding is visible

## Validation Test Cases

### Test 1: Minimal Valid Payload
```json
{
  "recipientEmail": "test@example.com",
  "villageName": "Paris",
  "nuits": 3,
  "saison": "printemps",
  "dateDebut": "2026-04-01",
  "dateFin": "2026-04-04",
  "adultes": 1,
  "enfantsAges": [],
  "formule": "DP",
  "envKey": "",
  "perPersonPerDay": 50,
  "perDayFamily": 50,
  "total": 150,
  "perPerson": 150,
  "perAdultBase": 150,
  "totalAdults": 150,
  "childAmounts": [],
  "totalChildren": 0,
  "adhesion": 0,
  "staySubtotal": 150
}
```

### Test 2: Large Family
```json
{
  "recipientEmail": "family@example.com",
  "villageName": "Marseille",
  "nuits": 14,
  "saison": "ete",
  "dateDebut": "2026-08-01",
  "dateFin": "2026-08-15",
  "adultes": 3,
  "enfantsAges": [2, 5, 8, 11, 14],
  "formule": "PC",
  ...full data...
}
```

### Test 3: Invalid Email
- Should fail with 400 Bad Request
- Message: "Validation error"

### Test 4: Brevo API Down
- Should fail with 502 Bad Gateway
- Message: "Email delivery failed"

## Debugging Tips

### View rendered HTML
```python
from apps.mailer.email_builder import build_html
from django.template.loader import render_to_string

data = {...}
html = build_html(data)

# Write to file for inspection
with open('/tmp/email.html', 'w') as f:
    f.write(html)

# Then open in browser
# file:///tmp/email.html
```

### Test template rendering
```python
from django.template.loader import render_to_string
from apps.mailer.email_builder import _prepare_template_context

data = {...}
context = _prepare_template_context(data)

# Check context keys
print(context.keys())

# Render template
html = render_to_string('mailer/vacation_budget_email.html', context)
```

### Check Brevo logs
```python
import logging
logging.getLogger('apps.mailer.brevo_client').setLevel(logging.DEBUG)

# Then make request
```
