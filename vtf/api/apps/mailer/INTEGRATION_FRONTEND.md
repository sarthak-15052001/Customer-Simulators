# Frontend Integration Guide - VTF Mailer Service

## Overview

The VTF mailer service allows you to send branded vacation-budget simulation emails to customers via the REST API. This guide shows how to integrate the mailer from your React/TypeScript frontend.

## API Endpoint

```
POST /api/v1/mailer/send-simulation
Content-Type: application/json
```

## Request Schema

```typescript
interface SendSimulationRequest {
  // Recipient info
  recipientEmail: string;          // email@example.com
  locale?: 'FR' | 'EN';            // Default: 'FR'
  bookingUrl?: string;             // https://www.vtf-vacances.com/booking/...

  // Destination / stay
  villageName: string;             // "Biarritz"
  nuits: number;                   // 7
  saison: string;                  // "ete", "printemps", etc.
  dateDebut: string;               // "2026-07-12" (ISO format)
  dateFin: string;                 // "2026-07-19" (ISO format)

  // Family
  adultes: number;                 // 2
  enfantsAges?: number[];          // [8, 5]

  // Formula / context
  formule: string;                 // "PC" (Pension Complète), "DP", etc.
  envKey?: string;                 // "mer", "montagne", "campagne", "ville"

  // Per-person summary
  perPersonPerDay: number;         // 86 (in €)
  perDayFamily: number;            // 612 (in €)
  total: number;                   // 4280 (in €)
  perPerson: number;               // 1070 (in €)

  // Budget breakdown
  perAdultBase: number;            // 595 (in €)
  totalAdults: number;             // 1190 (in €)
  childAmounts?: number[];         // [420, 420] (in €)
  totalChildren: number;           // 840 (in €)
  adhesion: number;                // 44 (in €)
  staySubtotal: number;            // 2074 (in €)

  // Optional cost buckets
  activitiesTotal?: number;        // 320 (in €)
  restoTotal?: number;             // 180 (in €)

  // Transport
  transportMode?: string;          // "car", "train", "plane", "bus"
  transportKm?: number;            // 400
  transportTotal?: number;         // 245 (in €)

  // Savings vs hotel
  hotelEstimate?: number;          // 5890 (in €)
  hotelSavings?: number;           // 1610 (in €)
  savingsPct?: number;             // 27 (percentage)
}
```

## Response Schema

### Success (200 OK)
```typescript
interface SuccessResponse {
  success: true;
  message: "Simulation email sent.";
  data: {
    messageId: string;             // Brevo message ID
    recipient: string;             // email@example.com
  }
}
```

### Error (400 Bad Request)
```typescript
interface ValidationErrorResponse {
  success: false;
  error: "Validation error.";
  detail: string;
}
```

### Error (502 Bad Gateway)
```typescript
interface BrevoErrorResponse {
  success: false;
  error: "Email delivery failed.";
  detail: string;
}
```

## Implementation Examples

### React Hook - useSendSimulationEmail

```typescript
// hooks/useSendSimulationEmail.ts

import { useState } from 'react';
import { api } from '@/api/client';

interface SendSimulationRequest {
  // ... (see schema above)
}

interface SendSimulationResponse {
  messageId: string;
  recipient: string;
}

export function useSendSimulationEmail() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (data: SendSimulationRequest): Promise<SendSimulationResponse | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/mailer/send-simulation', data);
      
      if (!response.data.success) {
        throw new Error(response.data.detail || response.data.error);
      }

      return response.data.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send email';
      setError(message);
      console.error('Mailer API error:', err);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { send, loading, error };
}
```

### Component - Email Trigger Button

```typescript
// components/SendSimulationEmailButton.tsx

import React from 'react';
import { useSendSimulationEmail } from '@/hooks/useSendSimulationEmail';
import { SimulationData } from '@/types/simulation';

interface Props {
  simulationData: SimulationData;
  recipientEmail: string;
  onSuccess?: (messageId: string) => void;
  onError?: (error: string) => void;
}

export function SendSimulationEmailButton({
  simulationData,
  recipientEmail,
  onSuccess,
  onError,
}: Props) {
  const { send, loading, error } = useSendSimulationEmail();

  const handleClick = async () => {
    // Build request payload
    const payload = {
      recipientEmail,
      locale: 'FR',
      bookingUrl: buildBookingUrl(simulationData),
      villageName: simulationData.location.name,
      nuits: simulationData.nights,
      saison: simulationData.season,
      dateDebut: formatDate(simulationData.startDate),
      dateFin: formatDate(simulationData.endDate),
      adultes: simulationData.adults,
      enfantsAges: simulationData.children.map(c => c.age),
      formule: simulationData.formula.code,
      envKey: simulationData.location.environment,
      perPersonPerDay: simulationData.pricing.perPersonPerDay,
      perDayFamily: simulationData.pricing.perDayFamily,
      total: simulationData.pricing.total,
      perPerson: simulationData.pricing.perPerson,
      perAdultBase: simulationData.pricing.perAdultBase,
      totalAdults: simulationData.pricing.totalAdults,
      childAmounts: simulationData.children.map(c => c.amount),
      totalChildren: simulationData.pricing.totalChildren,
      adhesion: simulationData.pricing.adhesion,
      staySubtotal: simulationData.pricing.staySubtotal,
      activitiesTotal: simulationData.pricing.activities || 0,
      restoTotal: simulationData.pricing.meals || 0,
      transportMode: simulationData.transport.mode,
      transportKm: simulationData.transport.km,
      transportTotal: simulationData.transport.cost || 0,
      hotelEstimate: simulationData.comparison.hotelPrice || 0,
      hotelSavings: simulationData.comparison.savings || 0,
      savingsPct: simulationData.comparison.savingsPercent || 0,
    };

    const result = await send(payload);
    
    if (result) {
      onSuccess?.(result.messageId);
      alert(`Email sent successfully to ${result.recipient}`);
    } else {
      onError?.(error || 'Unknown error');
      alert(`Failed to send email: ${error}`);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="btn btn-primary"
    >
      {loading ? 'Sending...' : 'Send by Email'}
    </button>
  );
}

// Helpers
function buildBookingUrl(data: SimulationData): string {
  const params = new URLSearchParams({
    village: data.location.id,
    dateDebut: formatDate(data.startDate),
    dateFin: formatDate(data.endDate),
    adultes: String(data.adults),
    enfants: data.children.map(c => c.age).join(','),
    formule: data.formula.code,
  });
  return `https://www.vtf-vacances.com/booking?${params.toString()}`;
}

function formatDate(date: Date | string): string {
  if (typeof date === 'string') return date;
  return date.toISOString().split('T')[0]; // ISO format: YYYY-MM-DD
}
```

### Full Page Integration

```typescript
// pages/SimulationPreview.tsx

import React, { useState } from 'react';
import { SimulationData } from '@/types/simulation';
import { SendSimulationEmailButton } from '@/components/SendSimulationEmailButton';
import { useSimulation } from '@/contexts/SimulationContext';

export function SimulationPreview() {
  const { simulation } = useSimulation();
  const [recipientEmail, setRecipientEmail] = useState('');
  const [emailSent, setEmailSent] = useState(false);

  if (!simulation) {
    return <div>No simulation data</div>;
  }

  const handleEmailSuccess = (messageId: string) => {
    setEmailSent(true);
    console.log('Email sent with messageId:', messageId);
    // Optionally clear form or show confirmation
    setTimeout(() => setEmailSent(false), 3000);
  };

  const handleEmailError = (error: string) => {
    console.error('Email error:', error);
    // Show error toast/modal
  };

  return (
    <div className="simulation-preview">
      <h1>My Vacation Simulation</h1>

      {/* Budget Summary Display */}
      <div className="budget-summary">
        <p>Budget: {simulation.pricing.total}€</p>
        <p>Location: {simulation.location.name}</p>
        <p>Dates: {simulation.startDate} to {simulation.endDate}</p>
      </div>

      {/* Email Form */}
      <div className="email-section">
        <h2>Share this simulation</h2>
        
        <input
          type="email"
          placeholder="your-email@example.com"
          value={recipientEmail}
          onChange={(e) => setRecipientEmail(e.target.value)}
          disabled={emailSent}
        />

        <SendSimulationEmailButton
          simulationData={simulation}
          recipientEmail={recipientEmail}
          onSuccess={handleEmailSuccess}
          onError={handleEmailError}
        />

        {emailSent && (
          <p className="success-message">
            Email sent! Check your inbox.
          </p>
        )}
      </div>

      {/* PDF Download Option (Future) */}
      <div className="download-section">
        <button className="btn btn-secondary">
          Download as PDF
        </button>
      </div>
    </div>
  );
}
```

### API Client Configuration

```typescript
// api/client.ts

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for auth token (if needed)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 502) {
      console.error('Brevo email delivery failed');
    }
    return Promise.reject(error);
  }
);
```

## Error Handling

### Common Errors & Solutions

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Invalid email format | 400 | `recipientEmail` is not valid | Check email format |
| Missing required field | 400 | Required field missing from payload | Verify all required fields |
| Invalid date format | 400 | Date not in ISO format (YYYY-MM-DD) | Use ISO format for dates |
| Email delivery failed | 502 | Brevo API error | Check API key, retry later |
| Template not found | 500 | Django template missing | Check server logs |

### Retry Strategy

```typescript
async function sendWithRetry(
  data: SendSimulationRequest,
  maxRetries = 3
): Promise<SendSimulationResponse | null> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await api.post('/mailer/send-simulation', data);
      return response.data.data;
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      
      // Exponential backoff
      await new Promise(resolve => 
        setTimeout(resolve, Math.pow(2, i) * 1000)
      );
    }
  }
  return null;
}
```

## Testing

### Unit Test Example

```typescript
// __tests__/SendSimulationEmailButton.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SendSimulationEmailButton } from '@/components/SendSimulationEmailButton';
import * as mailerHook from '@/hooks/useSendSimulationEmail';

jest.mock('@/hooks/useSendSimulationEmail');

describe('SendSimulationEmailButton', () => {
  it('should call send with correct payload', async () => {
    const mockSend = jest.fn();
    (mailerHook.useSendSimulationEmail as jest.Mock).mockReturnValue({
      send: mockSend,
      loading: false,
      error: null,
    });

    const mockData = {
      location: { name: 'Biarritz', environment: 'mer' },
      nights: 7,
      season: 'ete',
      // ... other fields
    };

    render(
      <SendSimulationEmailButton
        simulationData={mockData}
        recipientEmail="test@example.com"
        onSuccess={jest.fn()}
      />
    );

    fireEvent.click(screen.getByText('Send by Email'));

    await waitFor(() => {
      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          recipientEmail: 'test@example.com',
          villageName: 'Biarritz',
        })
      );
    });
  });

  it('should handle errors', async () => {
    const mockError = 'Email delivery failed';
    const mockOnError = jest.fn();

    (mailerHook.useSendSimulationEmail as jest.Mock).mockReturnValue({
      send: jest.fn(),
      loading: false,
      error: mockError,
    });

    render(
      <SendSimulationEmailButton
        simulationData={mockData}
        recipientEmail="test@example.com"
        onError={mockOnError}
      />
    );

    fireEvent.click(screen.getByText('Send by Email'));

    await waitFor(() => {
      expect(mockOnError).toHaveBeenCalledWith(mockError);
    });
  });
});
```

## Troubleshooting

### Email Not Received
1. Check spam/junk folder
2. Verify email address is correct
3. Check Brevo dashboard for delivery logs
4. Ensure API key is valid (check server logs)

### Invalid Request (400)
1. Verify all required fields are present
2. Check date format is ISO (YYYY-MM-DD)
3. Check numbers are integers (not strings)
4. Validate email format

### Delivery Failed (502)
1. Wait a few minutes and retry
2. Check Brevo API status
3. Verify API key hasn't expired
4. Check IP allowlist if enabled

## Best Practices

1. **Validate before sending**: Use the serializer schema for frontend validation
2. **Show loading state**: Disable button during request
3. **Handle errors gracefully**: Show user-friendly error messages
4. **Log analytics**: Track email sends for metrics
5. **Implement retry logic**: Handle temporary API failures
6. **Test with real emails**: Verify delivery to actual mailbox
7. **Monitor delivery**: Track unsubscribes and bounces via Brevo

## Environment Variables

```bash
# .env (frontend)
REACT_APP_API_URL=http://localhost:8000/api/v1

# .env (production)
REACT_APP_API_URL=https://api.vtf-vacances.com/api/v1
```

## Performance Considerations

- Email generation is fast (~50-100ms)
- Brevo API typically responds in 1-2 seconds
- Add loading indicator for UX
- Consider debouncing multiple clicks on send button
- Implement rate limiting on frontend to prevent abuse
