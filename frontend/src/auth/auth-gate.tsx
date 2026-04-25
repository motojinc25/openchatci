/**
 * AuthGate (CTR-0091, PRP-0050).
 *
 * Wraps any children that require an authenticated principal in
 * commercial mode. Mounted only when `VITE_AUTH_PROVIDER === 'msal'`
 * via the conditional routing in `App.tsx`; the OSS build never
 * imports this module at runtime because it lives behind a dynamic
 * import barrier.
 *
 * Behavior:
 *   - `inProgress !== 'none'`: render a minimal "Signing in..."
 *     placeholder so MSAL handshakes do not flash the gated content.
 *   - `isAuthenticated`: pass through.
 *   - Otherwise: redirect to `/signin` with the originally-requested
 *     path preserved as `state.from` for an optional return-to-URL
 *     handler later.
 */

import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

interface AuthGateProps {
  children: ReactNode
}

export function AuthGate({ children }: AuthGateProps) {
  const isAuthenticated = useIsAuthenticated()
  const { inProgress } = useMsal()
  const location = useLocation()

  if (inProgress !== 'none') {
    return (
      <main
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif',
          color: '#444',
        }}>
        Signing in...
      </main>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
