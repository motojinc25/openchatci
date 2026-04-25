/**
 * Sign-In Page (CTR-0091, PRP-0050).
 *
 * Branded landing page rendered only when the OSS frontend is built
 * in commercial mode (`VITE_AUTH_PROVIDER === 'msal'`). Initiates
 * MSAL interactive sign-in via the redirect flow (rather than popup)
 * so modern Cross-Origin-Opener-Policy enforcement on
 * `login.microsoftonline.com` does not block the popup `window.closed`
 * probe.
 *
 * After Entra ID returns to the app, `bootstrapMsal()` (called by
 * `main.tsx`) completes the redirect and sets the active account;
 * the effect below then forwards the user to `/chat`.
 */

import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { brand } from '../auth/branding'
import { isMsalConfigured, loginRequest } from '../auth/msal-bootstrap'

interface SignInLocationState {
  from?: string
}

export function SignInPage() {
  const { instance, inProgress } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const navigate = useNavigate()
  const location = useLocation()
  const configured = isMsalConfigured()

  // Once MSAL settles a returning redirect (or finds a cached account),
  // route the user back to where they came from -- or /chat by default.
  useEffect(() => {
    if (isAuthenticated) {
      const state = location.state as SignInLocationState | null
      const target = state?.from && state.from !== '/signin' ? state.from : '/chat'
      navigate(target, { replace: true })
    }
  }, [isAuthenticated, location.state, navigate])

  const handleSignIn = async () => {
    if (!configured) {
      alert(
        'Commercial mode (VITE_AUTH_PROVIDER=msal) requires VITE_MSAL_TENANT_ID and ' +
          'VITE_MSAL_CLIENT_ID to be set in the SPA environment. Update your .env ' +
          'and restart the dev server (or rebuild for production).',
      )
      return
    }
    try {
      await instance.loginRedirect(loginRequest)
    } catch (err) {
      console.error('sign-in failed', err)
      alert(
        'Sign-in failed: ' +
          (err instanceof Error ? err.message : String(err)) +
          '\nCheck the browser console for details.',
      )
    }
  }

  const buttonDisabled = inProgress !== 'none'

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `linear-gradient(135deg, ${brand.primaryColor}, ${brand.accentColor})`,
        color: '#fff',
        fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif',
      }}>
      <section
        style={{
          maxWidth: 420,
          width: '90%',
          padding: '2.5rem',
          borderRadius: 16,
          background: 'rgba(0, 0, 0, 0.25)',
          backdropFilter: 'blur(8px)',
          textAlign: 'center',
        }}>
        <h1 style={{ marginBottom: '0.25em', fontSize: '2rem' }}>{brand.productName}</h1>
        {brand.tagline ? <p style={{ opacity: 0.85, marginTop: 0 }}>{brand.tagline}</p> : null}
        <button
          type="button"
          onClick={handleSignIn}
          disabled={buttonDisabled}
          style={{
            marginTop: '2rem',
            padding: '0.75rem 1.5rem',
            borderRadius: 8,
            border: 'none',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: buttonDisabled ? 'not-allowed' : 'pointer',
            opacity: buttonDisabled ? 0.6 : 1,
            background: '#fff',
            color: brand.primaryColor,
          }}>
          {buttonDisabled ? 'Signing in...' : 'Sign in with Microsoft'}
        </button>
      </section>
    </main>
  )
}
