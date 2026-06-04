# BomiPay Ops Intelligence Dashboard

A production-quality operational intelligence dashboard for the BomiPay Nigerian payment platform. Built with a Palantir/Datadog/Grafana aesthetic — dark, information-dense, operational.

## Tech Stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** — dark operational theme
- **TanStack Query v5** — data fetching with cache + placeholder data
- **Zustand** — auth & global state
- **Recharts** — charts, sparklines, area charts
- **React Flow** — payment graph visualization
- **Lucide React** — icons

## Getting Started

### 1. Install dependencies

```bash
cd bomipay-website
npm install
```

### 2. Configure environment

```bash
cp .env.local.example .env.local
```

Edit `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 3. Start development server

```bash
npm run dev
```

Open http://localhost:3000 — redirects to `/dashboard`.

### 4. Production build

```bash
npm run build
npm start
```

## Pages

| Route | Description |
|-------|-------------|
| `/login` | JWT authentication |
| `/dashboard` | Mission Control — KPIs, provider health, AI insight |
| `/timeline` | Unified payment event timeline with infinite scroll |
| `/incidents` | Incident management with severity triage |
| `/reconciliation` | Provider vs bank statement matching |
| `/actions` | Prioritized operational task list |
| `/providers` | Provider health metrics + 30-day history |
| `/graph` | Payment graph explorer (React Flow) |
| `/ai` | AI operations assistant (chat interface) |

## Mock Data

All pages render with **mock placeholder data** when the backend API is unavailable, via TanStack Query `placeholderData`.

## Authentication

- Login at `/login` with email + password
- JWT stored in `localStorage` + Zustand persisted state
- Axios interceptor auto-attaches `Authorization: Bearer <token>`
- 401 responses trigger automatic logout

## Utilities

```typescript
import { formatNGN, bpsToPercent, formatDate } from '@/lib/utils'

formatNGN(4500000)     // "?45,000.00"  (minor units = kobo)
bpsToPercent(9950)     // "99.50%"       (basis points)
formatDate(isoString)  // Lagos timezone formatted date
```
