# PrecisionPulse Frontend

Next.js web dashboard for real-time telemetry monitoring with responsive design and zero-refresh UI.

## Features

- Real-time telemetry dashboard
- Responsive design (mobile, tablet, desktop)
- Zero-refresh parameter updates
- Role-based access control
- Live data streaming with charts
- Parameter management interface

## Quick Start

### Prerequisites
- Node.js 16+
- npm or yarn

### Installation

```bash
# Clone repository
git clone https://github.com/DevAngles-Interns-2026/dspl-precision-pulse-frontend.git
cd dspl-precision-pulse-frontend

# Install dependencies
npm install
# or
yarn install
```

### Configuration

Create `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:5000
NEXT_PUBLIC_SOCKET_URL=http://localhost:5000
```

### Development

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@precisionpulse.com | admin123 |
| Client | client@precisionpulse.com | client123 |
| User | user@precisionpulse.com | user123 |

## Project Structure

```
dspl-precision-pulse-frontend/
├── src/
│   ├── app/              # Next.js pages and layouts
│   ├── components/       # Reusable UI components
│   ├── services/         # API and data services
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities and helpers
│   └── models/           # TypeScript interfaces
├── public/               # Static assets
├── docs/                 # Documentation
├── package.json
└── next.config.ts
```

## Pages

- **Login** (`/login`) - User authentication
- **Dashboard** (`/dashboard`) - Real-time telemetry display
- **Parameters** (`/parameters`) - Parameter configuration
- **Users** (`/users`) - User management (admin only)
- **Profile** (`/profile`) - User profile settings

## Key Features

### Responsive Design
- Mobile-first approach
- Adaptive layouts for all screen sizes
- Responsive tables with hidden columns on small screens

### Zero-Refresh UI
- Parameter updates without page reload
- Instant status changes
- Smooth user experience

### Real-Time Updates
- Live telemetry data streaming
- Auto-updating charts
- WebSocket integration

## API Integration

Frontend connects to backend at `http://localhost:5000`:

- `POST /api/auth/login` - User login
- `GET /api/parameters` - Fetch parameters
- `PUT /api/parameters/:id` - Update parameter
- `GET /api/telemetry/latest` - Get latest telemetry data

## Technologies

- **Framework**: Next.js 16+
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React Hooks
- **HTTP**: Fetch API
- **Real-time**: Socket.IO

## Development

### Code Style
- Follow ESLint configuration
- Use TypeScript for type safety
- Format with Prettier

### Testing
```bash
npm run lint
```

## Troubleshooting

**Port 3000 already in use:**
```bash
npm run dev -- -p 3001
```

**API connection fails:**
- Verify backend is running on `http://localhost:5000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`

**Build errors:**
- Clear `.next` folder: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`

## License

MIT License - See LICENSE file

## Support

For issues and questions, contact the development team.
