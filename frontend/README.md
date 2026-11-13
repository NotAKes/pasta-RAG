# Pastabar frontend

React/Vite, shared same-origin API client, optional Telegram Web App adapter.
Run backend on port 8000, then `npm ci && npm run dev`.

- `npm run lint`: ESLint and React hooks checks.
- `npm test`: Node built-in test runner for API contracts and cart/order helpers.
- `npm run build`: emits both `dist/index.html` and `dist/admin.html`.

`VITE_API_BASE_URL` is optional and build-time; omit it for normal same-origin hosting.
Never put secrets into Vite variables: they are public browser code.
See the root README for architecture, offline demo and deployment/migration details.
