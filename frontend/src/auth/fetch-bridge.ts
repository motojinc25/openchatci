/**
 * Same-Origin Token Bridge (CTR-0089, CTR-0091, PRP-0050).
 *
 * Wraps `window.fetch` once at SPA startup so every same-origin
 * request issued by OSS chat components carries an
 * `Authorization: Bearer <token>` acquired via `@azure/msal-browser`.
 * Cross-origin traffic (CDN, fonts, analytics, MSAL discovery) passes
 * through unchanged.
 *
 * The module is loaded only when `VITE_AUTH_PROVIDER === 'msal'`
 * (CTR-0091); the OSS default build never imports MSAL packages so
 * Vite tree-shake removes them entirely. Ownership: CAP-001 Chat
 * Frontend (transferred from CAP-006 by PRP-0050).
 *
 * Token acquisition strategy:
 *   1. `acquireTokenSilent` from MSAL session storage cache.
 *   2. On 401 response, retry once with `forceRefresh: true`.
 *   3. If refresh fails or the second attempt also returns 401,
 *      dispatch `chatci:session-expired` and redirect to `/signin`.
 */

import {
  type AuthenticationResult,
  InteractionRequiredAuthError,
  type PublicClientApplication,
  type SilentRequest,
} from '@azure/msal-browser'

const BRIDGE_INSTALLED = Symbol.for('chatci.fetchBridgeInstalled')

interface BridgedWindow extends Window {
  [BRIDGE_INSTALLED]?: true
}

/**
 * Resolve the API scope requested when acquiring tokens silently.
 * Defaults to `VITE_MSAL_API_SCOPE`, then falls back to
 * `api://<VITE_MSAL_CLIENT_ID>/.default` for callers who only set the
 * client id.
 */
function resolveApiScope(): string {
  const explicit = import.meta.env.VITE_MSAL_API_SCOPE ?? ''
  if (typeof explicit === 'string' && explicit.trim().length > 0) {
    return explicit.trim()
  }
  const clientId = (import.meta.env.VITE_MSAL_CLIENT_ID ?? '') as string
  return clientId ? `api://${clientId}/.default` : ''
}

const API_SCOPE = resolveApiScope()

/**
 * Resolve the API origin against which Bearer attachment should run.
 *
 * Defaults to `window.location.origin` (same-origin SPA + API). When
 * the operator runs the SPA on a different origin than the API
 * (typical of the dev pair: SPA :5173, backend :8000), set
 * `VITE_API_BASE_URL` to the API base so the bridge knows which
 * origin to decorate.
 */
function resolveApiOrigin(): string {
  const explicit = import.meta.env.VITE_API_BASE_URL ?? ''
  if (typeof explicit === 'string' && explicit.trim().length > 0) {
    try {
      return new URL(explicit).origin
    } catch {
      // fall through to same-origin default
    }
  }
  return window.location.origin
}

const API_ORIGIN = resolveApiOrigin()

/**
 * Install the same-origin token bridge.
 *
 * Idempotent: subsequent calls do nothing so HMR-induced double
 * mounts in dev mode do not stack wrappers.
 */
export function installFetchBridge(instance: PublicClientApplication): void {
  const w = window as BridgedWindow
  if (w[BRIDGE_INSTALLED]) {
    return
  }

  const original = window.fetch.bind(window)

  window.fetch = async (input, init = {}) => {
    const url = describeUrl(input)
    if (!isSameOriginRequest(input)) {
      return original(input, init)
    }

    const headers = mergeHeaders(input, init)
    const token = await acquireAccessToken(instance)
    if (token) {
      ensureAuthorization(headers, token)
    } else {
      console.warn('no token attached to', url, {
        hasActiveAccount: Boolean(instance.getActiveAccount()),
        accountCount: instance.getAllAccounts().length,
        apiScope: API_SCOPE || '(none)',
      })
    }

    const firstResponse = await original(input, { ...init, headers })
    if (firstResponse.status !== 401) {
      return firstResponse
    }
    console.warn('401 on first attempt', url, { hadToken: Boolean(token) })

    // First 401: try a forced silent refresh exactly once.
    const refreshed = await acquireAccessToken(instance, { forceRefresh: true })
    if (!refreshed) {
      console.warn('silent refresh returned no token; redirecting to /signin')
      notifyAndRedirectToSignIn()
      return firstResponse
    }

    ensureAuthorization(headers, refreshed)
    const secondResponse = await original(input, { ...init, headers })
    if (secondResponse.status === 401) {
      // Two consecutive 401s -> the refreshed token is also rejected.
      // Surface a session-expired event and bounce to /signin.
      console.warn('401 after refresh; redirecting to /signin')
      notifyAndRedirectToSignIn()
    }
    return secondResponse
  }

  w[BRIDGE_INSTALLED] = true
}

function describeUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return (input as Request).url
}

/**
 * Strict same-origin check against the configured API origin.
 *
 * `Request` instances expose a fully resolved URL via the `url`
 * property; string inputs are resolved against
 * `window.location.href`. Anything that fails to parse is treated as
 * cross-origin so the bridge never accidentally leaks a Bearer
 * header to an unrelated host.
 */
export function isSameOriginRequest(input: RequestInfo | URL): boolean {
  try {
    let url: URL
    if (typeof input === 'string') {
      url = new URL(input, window.location.href)
    } else if (input instanceof URL) {
      url = input
    } else {
      url = new URL((input as Request).url)
    }
    return url.origin === API_ORIGIN
  } catch {
    return false
  }
}

/**
 * Build a mutable `Headers` object from the incoming fetch arguments.
 *
 * `init.headers` wins over `Request.headers` because the caller's
 * intent is the most-recent value.
 */
function mergeHeaders(input: RequestInfo | URL, init: RequestInit): Headers {
  const headers = new Headers()
  if (input instanceof Request) {
    input.headers.forEach((value, key) => {
      headers.append(key, value)
    })
  }
  if (init.headers) {
    new Headers(init.headers as HeadersInit).forEach((value, key) => {
      headers.set(key, value)
    })
  }
  return headers
}

function ensureAuthorization(headers: Headers, token: string): void {
  // The caller may have already set Authorization (e.g. an API tester
  // probing the strict /v1/responses endpoint with a custom key);
  // respect that explicit value and do not overwrite it.
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
}

interface AcquireOptions {
  forceRefresh?: boolean
}

async function acquireAccessToken(
  instance: PublicClientApplication,
  opts: AcquireOptions = {},
): Promise<string | null> {
  const account = instance.getActiveAccount() ?? instance.getAllAccounts()[0]
  if (!account || !API_SCOPE) {
    return null
  }
  const request: SilentRequest = {
    scopes: [API_SCOPE],
    account,
    forceRefresh: opts.forceRefresh ?? false,
  }
  try {
    const result: AuthenticationResult = await instance.acquireTokenSilent(request)
    return result.accessToken || null
  } catch (err) {
    if (err instanceof InteractionRequiredAuthError) {
      // Silent acquisition cannot succeed without user interaction.
      return null
    }
    // Network or unexpected error -- treat as no token; the caller
    // path falls through to a 401 -> redirect.
    console.warn('silent token acquisition failed', err)
    return null
  }
}

function notifyAndRedirectToSignIn(): void {
  if (typeof window === 'undefined') {
    return
  }
  // Surface the session-expired event as a window-scoped
  // notification so a future toast layer can subscribe; the
  // redirect happens immediately afterwards.
  window.dispatchEvent(
    new CustomEvent('chatci:session-expired', {
      detail: { reason: 'msal-401-after-refresh' },
    }),
  )
  if (window.location.pathname !== '/signin') {
    window.location.replace('/signin')
  }
}
