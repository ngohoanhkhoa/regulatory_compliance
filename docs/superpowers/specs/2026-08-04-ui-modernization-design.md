# UI Modernization & Component Library Design

> Date: 2026-08-04
> Scope: Frontend UI/UX overhaul for EU Regulatory Compliance RAG Chatbot

## Current State

The frontend is a single-page React app (Vite + React 18 + React Router) with:
- **Pages**: Login, Chat, History, Settings
- **Styling**: One 414-line CSS file (`main.css`) with CSS custom properties for a dark theme
- **Components**: No reusable components — everything is inline in pages
- **Icons**: Emoji-based (📋, ✓, 👍, ⚠, etc.)
- **No icon library installed**

## Goals

1. Install `lucide-react` for consistent, professional iconography
2. Build a small reusable component library (Button, Card, Badge, Input, Toggle, IconButton)
3. Modernize the Navbar with icons, active states, and a user dropdown
4. Redesign Login with better visual hierarchy and iconography
5. Redesign Chat with a sidebar layout, improved message bubbles, and a polished sources panel
6. Redesign History with search/filter and improved cards
7. Expand Settings with more options (theme, notifications, chat preferences)
8. Add a Dashboard page with user stats (query count, grounded ratio, recent activity)
9. Improve CSS with a better design system (spacing scale, typography scale, shadow scale)
10. Ensure responsive design (mobile-friendly navbar, collapsible sidebar, flexible grids)

## Architecture

### Component Library (`frontend/src/components/`)

A flat folder of presentational components. Each component:
- Accepts `className` for override
- Uses the design system CSS variables
- Has no business logic (pure UI)

Components:
- `Button` — variants: primary, secondary, ghost, danger; sizes: sm, md, lg
- `Card` — with optional header, footer, and hover elevation
- `Badge` — variants: default, success, warning, error, info
- `Input` — with label, error state, icon prefix/suffix
- `Toggle` — accessible switch (replaces current raw CSS toggle)
- `IconButton` — square button for icon-only actions

### Design System CSS Updates

Expand `:root` with:
- `--space-*` scale (1-8 steps)
- `--font-size-*` scale
- `--shadow-*` scale (shadow-sm, shadow, shadow-md, shadow-lg)
- Keep existing color palette (dark theme is well-designed)

### Page Restructuring

| Page | Changes |
|------|---------|
| **Login** | Add icons to inputs, improve tab buttons with IconButton, add brand logo area |
| **Chat** | Add left sidebar for conversation list/history; improve message bubbles with avatar indicators; redesign sources panel as a right drawer or accordion; add message timestamps |
| **History** | Add search bar (Input with search icon); add filter badges (date range, grounded status); improve card layout with metadata chips |
| **Settings** | Add "Appearance" group (compact mode toggle); add "Chat" group (auto-scroll, enter-to-send); add "Notifications" group (toast position); organize into tabs or accordion |
| **Dashboard** | NEW page — stats cards (total queries, avg sources, grounded %), recent activity feed, quick-action buttons |

### Responsive Strategy

- **Mobile (< 768px)**: Navbar becomes hamburger menu; Chat sidebar becomes bottom sheet or hidden; History cards stack; Dashboard stats become 2-column grid
- **Tablet (768-1024px)**: Chat sidebar collapses to icons-only; Settings uses full width
- **Desktop (> 1024px)**: Full layout as designed

### New API Needs

For the Dashboard, we need a new backend endpoint. The `query_log` table already has all data:
- `GET /stats` — returns `{ total_queries, grounded_count, avg_sources, recent_queries[] }`
- This can be added to `routes_query.py` with a simple aggregation query

## Files to Create / Modify

### New Files
- `frontend/src/components/Button.jsx`
- `frontend/src/components/Card.jsx`
- `frontend/src/components/Badge.jsx`
- `frontend/src/components/Input.jsx`
- `frontend/src/components/Toggle.jsx`
- `frontend/src/components/IconButton.jsx`
- `frontend/src/components/Navbar.jsx` (extract from App.jsx)
- `frontend/src/components/AppRoutes.jsx` (extract from App.jsx)
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/EmptyState.jsx`
- `frontend/src/components/LoadingSpinner.jsx`
- `frontend/src/components/Toast.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/hooks/useMediaQuery.js`
- `frontend/src/hooks/useLocalStorage.js`
- `frontend/src/api/stats.js`
- `src/api/routes_stats.py` (backend)

### Modified Files
- `frontend/package.json` — add `lucide-react`
- `frontend/src/App.jsx` — extract NavBar, AppRoutes; add Dashboard route
- `frontend/src/styles/main.css` — expand design system
- `frontend/src/pages/Login.jsx` — use new components
- `frontend/src/pages/Chat.jsx` — add sidebar, use new components, redesign bubbles
- `frontend/src/pages/History.jsx` — add search/filter, use new components
- `frontend/src/pages/Settings.jsx` — expand settings, use Toggle component
- `frontend/src/api/settings.js` — add new setting keys
- `frontend/src/api/client.js` — add `getStats()`
- `src/api/routes_query.py` — add `/stats` endpoint (or new file)
- `src/api/main.py` — include stats router
- `src/api/schemas.py` — add StatsResponse schema
- `src/auth/models.py` — add `get_user_stats()`

## Dependencies

- `lucide-react` (^0.x) — tree-shakeable icon library

## Testing Strategy

- Visual regression: manually verify each page at 320px, 768px, 1440px
- Accessibility: all interactive elements must have focus states; toggles must be keyboard-accessible
- Functional: search/filter on History works; Dashboard loads stats; Settings persist to localStorage
