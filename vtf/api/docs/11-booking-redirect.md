# 11 — Booking redirect service

> Spec source: §US-2.8.
>
> The "Réserver sur VTF" button **never** points directly at vtf-vacances.com. It always
> goes through `GET /api/v1/go/{token}` which logs the click and 302s to the pre-filled
> VTF booking page. This is the single most important conversion-tracking signal.

## 1. Why a token-based redirect?

| Goal                                                  | How the token-redirect achieves it                              |
|-------------------------------------------------------|-----------------------------------------------------------------|
| Capture every click (conversion intent)               | One DB write per `GET /go/{token}` → `BookingClick` row         |
| Attribute the click to a specific simulation/reco     | Token payload carries `source`, `recoStrategy`, `recoScore`     |
| Survive VTF URL changes                               | We control the redirect target — swap once, no client change    |
| Never dead-end the user                               | Expired/tampered tokens still redirect (to the village's generic page) |
| Avoid leaking PII into the URL                        | Token is opaque; payload server-side                            |

## 2. Endpoints

### `POST /api/v1/villages/{id}/booking-link`

Mints a token and stores the full payload server-side. Frontend calls this **once per
result page render** (cheap — < 50 ms, no external calls).

**Request:**

```json
{
  "family": { "adultes": 2, "enfants": [{ "age": 2 }, { "age": 7 }, { "age": 13 }] },
  "dates":  { "debut": "2026-07-05", "fin": "2026-07-12" },
  "sessionId": "abc-123-def",
  "source": "estimate",
  "context": {
    "estimatedTotal": 2847,
    "formule": "PC",
    "promosApplied": ["qf_r1", "premiere_minute"],
    "recoStrategy": null,
    "recoScore": null,
    "recoRank": null
  }
}
```

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "redirectUrl": "https://api.example.com/api/v1/go/eyJhbGciOiJIUzI1NiJ9...",
  "expiresAt": "2026-07-08T23:59:59Z",
  "targetUrl": "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/pyrenees-atlantiques/biarritz/le-domaine-de-francon?…",
  "params": {
    "season": "summer",
    "nbPersons": 5,
    "nbAdults": 2,
    "nbBabies": 0,
    "nbChildren3": 1,
    "nbChildren1": 1,
    "nbChildren2": 1
  }
}
```

`bookingUrl` (= `redirectUrl`) is also embedded directly in:
- `POST /api/v1/estimate/stay` response
- `POST /api/v1/recommend/villages` response (one per village)
- `GET  /api/v1/villages/{id}/similar` response (one per village)

The view layer calls the token service **internally** (no extra HTTP round-trip):

```python
# Inside EstimateStayView.post()
token = BookingRedirectService.create_token(
    village=village,
    session_id=request.headers.get("X-Session-ID", ""),
    family=family,
    dates=dates,
    context={"source": "estimate", "estimatedTotal": result.total, ...},
)
response_data["bookingUrl"] = f"{settings.API_BASE_URL}/api/v1/go/{token}"
```

### `GET /api/v1/go/{token}`

The redirect endpoint. Behavior:

```
GET /api/v1/go/eyJhbGciOiJIUzI1NiJ9...
  │
  ▼
1. Decode + verify HMAC signature (constant-time compare)
2. Check expiry (default 72 h)
3. Load BookingRedirectToken payload from DB
4. Async: write BookingClick row (transaction.on_commit)
5. Return 302 Found, Location: <target_url>

If token is invalid or expired:
  → 302 to village's generic VTF page (no params) — never 404
```

**Performance budget:**
- Token verification: < 5 ms (HMAC-SHA-256, no DB)
- Total response: < 50 ms (DB write is async)

## 3. Token design

**Format:** `{nonce}.{exp_unix}.{sig_short}` — opaque to the client, NOT a JWT.

| Component  | Content                                          | Length       |
|------------|--------------------------------------------------|--------------|
| `nonce`    | `secrets.token_urlsafe(16)`                      | 22 chars     |
| `exp_unix` | Unix timestamp of expiry                         | 10 chars     |
| `sig_short`| First 32 chars of HMAC-SHA-256                   | 32 chars     |

**Body that's signed:**
```
{village_id}|{session_id}|{payload_hash}|{exp_unix}|{nonce}
```

The full payload (`family`, `dates`, `context`) lives **server-side** in
`BookingRedirectToken.payload`. The token is just a lookup key.

**Why HMAC, not JWT?**
- Smaller (no JSON header), no public-key decoding cost
- We're not federating; we control both signer and verifier
- Tampering is impossible without the secret (`BOOKING_REDIRECT_SECRET` env var)

**Rotation:** rotate `BOOKING_REDIRECT_SECRET` quarterly. During rotation, accept tokens
signed with either the current or previous secret (dual-key window of 72 h = TTL).

## 4. Click logging

Every `GET /go/{token}` produces a `BookingClick` row (see `03-data-models.md`):

```python
# apps/pricing/views.py
class BookingRedirectView(View):
    """GET /api/v1/go/{token} — public redirect endpoint, no auth."""

    def get(self, request, token: str):
        try:
            row = BookingRedirectToken.objects.get(token=token)
            if row.expires_at < timezone.now():
                raise BookingRedirectToken.DoesNotExist
            verified = booking_url.verify_token(
                token,
                village_id=row.village_id,
                session_id=row.session_id,
                payload_hash=booking_url.hash_payload(row.payload),
            )
            if not verified:
                raise BookingRedirectToken.DoesNotExist
        except BookingRedirectToken.DoesNotExist:
            # Fallback: redirect to the village's generic page (never 404)
            village_id = _try_extract_village_id(token)
            target = _generic_vtf_url(village_id) if village_id else "https://www.vtf-vacances.com/fr_FR/"
            return HttpResponseRedirect(target)

        # Async: log the click after the response is committed
        is_repeat = row.click_count > 0
        transaction.on_commit(lambda: _log_booking_click(row, request, is_repeat))
        BookingRedirectToken.objects.filter(pk=token).update(click_count=F("click_count") + 1)

        return HttpResponseRedirect(row.target_url)


def _log_booking_click(row, request, is_repeat: bool) -> None:
    payload = row.payload
    BookingClick.objects.create(
        token=row.token,
        session_id=row.session_id,
        village=row.village,
        source=payload.get("context", {}).get("source", "estimate"),
        family_adults=payload["family"]["adultes"],
        family_children=payload["family"]["enfants"],
        date_debut=payload["dates"]["debut"],
        date_fin=payload["dates"]["fin"],
        saison_key=payload.get("context", {}).get("saisonKey", ""),
        formule=payload.get("context", {}).get("formule", ""),
        estimated_total=payload.get("context", {}).get("estimatedTotal"),
        promos_applied=payload.get("context", {}).get("promosApplied", []),
        reco_strategy=payload.get("context", {}).get("recoStrategy", ""),
        reco_score=payload.get("context", {}).get("recoScore"),
        reco_rank=payload.get("context", {}).get("recoRank"),
        ip_hash=hashlib.sha256(
            (get_client_ip(request) + settings.SECRET_IP_SALT).encode()
        ).hexdigest(),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
        is_repeat=is_repeat,
    )
```

## 5. Analytics queries enabled

| Question                                                        | Query                                                                                                     |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| Simulator → booking click conversion rate                       | `BookingClick.count() / VillageInteraction.filter(kind='simulate').count()`                              |
| Which villages convert best from recommendations                | `BookingClick.filter(source='recommendation').values('village').annotate(n=Count('id')).order_by('-n')`  |
| Does recommendation rank correlate with clicks?                 | `BookingClick.filter(reco_rank__isnull=False).aggregate(avg_rank=Avg('reco_rank'))`                       |
| Which promos drive the most booking intent?                     | `BookingClick.values('promos_applied').annotate(n=Count('id'))`                                          |
| Family profiles that click but aren't recommended their village | Cross-join `BookingClick × reco logs`                                                                     |
| Average estimated budget of users who click through             | `BookingClick.aggregate(avg=Avg('estimated_total'))`                                                      |
| Does QF eligibility increase CTR?                               | `BookingClick.filter(promos_applied__contains=['qf_r1'])` vs control                                       |

## 6. Privacy

- IP hashed with `SECRET_IP_SALT` (`sha256(ip + salt)`)
- User-Agent truncated to 256 chars (no PII risk)
- Session ID is anonymous (random UUID)
- Token expires in 72 h; full token row purged after 90 d via cleanup cron
- `BookingClick` retained 90 d hot + 1 y aggregated (then deleted)

GDPR right-to-erasure: user provides a session ID → we delete all rows where
`session_id == ?` (rare; UI doesn't currently expose this).

## 7. Acceptance criteria

| ID         | Criterion                                                                  |
|------------|----------------------------------------------------------------------------|
| (US-2.8.1) | `GET /api/v1/go/{token}` returns 302 with correct `Location` header        |
| (US-2.8.2) | `BookingClick` row created on every redirect (async)                       |
| (US-2.8.3) | Expired token (> 72 h) still redirects to village generic page             |
| (US-2.8.4) | Invalid / tampered token redirects to VTF homepage — never a dead end      |
| (US-2.8.5) | Token generation < 10 ms (no network call)                                  |
| (US-2.8.6) | Redirect response < 50 ms (DB write async via `on_commit`)                  |
| (US-2.8.7) | `bookingUrl` field present in estimate, recommendation, and similar responses |
| (US-2.8.8) | All 32 villages have `vtf_slug`, `vtf_department`, `vtf_city` populated     |
| (US-2.8.9) | Repeat clicks tracked with `is_repeat=True`                                |
| (US-2.8.10)| IP is hashed, no PII stored beyond `session_id`                            |

## 8. Failure modes & mitigation

| Failure                                              | What happens                                            | Mitigation                              |
|------------------------------------------------------|---------------------------------------------------------|-----------------------------------------|
| `BOOKING_REDIRECT_SECRET` rotated mid-flight         | Token signed with old secret rejected                   | Dual-key window during rotation         |
| VTF URL structure changes                             | Targets become 404                                       | Weekly `verify_vtf_urls` cron + alert  |
| `BookingRedirectToken` table grows unbounded          | Storage costs                                           | Daily cleanup of expired rows           |
| `BookingClick` write fails (DB outage)                | Click is lost                                           | `transaction.on_commit` + Sentry alert  |
| Bot crawler hits `/go/*` repeatedly                   | Inflated click counts                                   | Rate limit + bot-pattern detection on UA |
| Frontend caches `bookingUrl` past expiry              | User clicks → expired token → fallback to generic page  | Acceptable degradation; not 404         |
