# Frontend API Architecture Specification

This document outlines the design and usage of the API layer in the VTF Simulator frontend.

## Goals
- **Scalability**: Easily add new features/endpoints without code duplication.
- **Maintainability**: Centralized configuration and types.
- **Debugging**: Structured logging for both development and production.
- **Type Safety**: End-to-end typing using TypeScript.

## Resources
- **Backend API Documentation**: [http://192.168.1.89:8000/api/docs/](http://192.168.1.89:8000/api/docs/)

## Architecture Components

### 1. Environment Configuration
- **Files**: `.env`, `.env.example`, `.env.production`
- **Purpose**: Manage the base host URL depending on the environment.
- **Usage**: Variable `VITE_API_URL` should point to the host only (e.g., `http://localhost:3000`).

### 2. Core API Client (`src/api/client.ts`)
- **Technology**: Axios
- **Features**: 
  - Base URL injection from `src/config/api.ts`.
  - Request Interceptors: Logging and custom header management.
  - Response Interceptors: Global error handling and logging.

### 3. Centralized Endpoints (`src/api/endpoints.ts`)
- **Purpose**: A single registry for all API relative paths.
- **Benefit**: No hardcoded URLs in components or services.

### 4. Feature modules (`src/features/<domain>/`)
- **Example**: `src/features/villages/village.api.ts` — `villageApi` (list + detail). `src/features/villages/region.api.ts` — `regionApi` (regions list + region activities).
- **Hooks**: `village.hooks.ts` (`useVillages`, `useVillageDetails`), `region.hooks.ts` (`useRegions`, `useRegionActivities`) — TanStack Query, delegating to the matching `*Api` modules.

### 5. Shared types (`src/types/api.ts`, …)
- **Purpose**: Cross-cutting types (e.g. `PaginatedResponse`) shared by feature APIs.

### 6. Logger Utility (`src/utils/logger.ts`)
- **Purpose**: Structured logging that changes behavior based on `PROD` vs `DEV` environments.

## Data Flow
`.env` (Host) → `API Config` → `Axios Client` → `Endpoints` → **`villageApi` / `regionApi`** → **`village.hooks` / `region.hooks`** → **Component**

## Example Usage

```tsx
import { useVillages } from '../features/villages/village.hooks';

function VillagesList() {
  const { data, isLoading, error } = useVillages({ env: 'sea', limit: 20, offset: 0, formule: 'PC' });

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error loading villages</p>;

  return (
     <ul>
       {data?.results.map(v => <li key={v.id}>{v.nom}</li>)}
     </ul>
  );
}
```
