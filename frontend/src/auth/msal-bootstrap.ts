/**
 * MSAL Bootstrap (CTR-0091, PRP-0050).
 *
 * Single-shot async setup of `@azure/msal-browser` for the OSS
 * frontend in commercial mode (`VITE_AUTH_PROVIDER === 'msal'`).
 *
 * Order matters under MSAL Browser v3+:
 *   1. `await PublicClientApplication.initialize()` -- mandatory; v3+
 *      auth APIs hang silently until init completes.
 *   2. `await instance.handleRedirectPromise()` -- completes the
 *      `loginRedirect` flow on return from Entra ID. The
 *      `@azure/msal-react` v2 MsalProvider does NOT auto-call this
 *      for us.
 *   3. `installFetchBridge(instance)` -- AFTER initialize so the very
 *      first OSS-component fetch attaches the Bearer token.
 *
 * The module is dynamic-imported only when the build flag is set
 * (CTR-0091), so OSS-mode bundles never pull in MSAL packages.
 */

import {
  type AuthenticationResult,
  type Configuration,
  EventType,
  type PopupRequest,
  PublicClientApplication,
} from '@azure/msal-browser'

import { installFetchBridge } from './fetch-bridge'

function buildMsalConfig(): Configuration {
  const tenantId = (import.meta.env.VITE_MSAL_TENANT_ID ?? '') as string
  const clientId = (import.meta.env.VITE_MSAL_CLIENT_ID ?? '') as string
  const redirectUri = (import.meta.env.VITE_MSAL_REDIRECT_URI as string | undefined) ?? window.location.origin

  return {
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId || 'common'}`,
      redirectUri,
      postLogoutRedirectUri: redirectUri,
      navigateToLoginRequestUrl: true,
    },
    cache: {
      cacheLocation: 'sessionStorage',
      storeAuthStateInCookie: false,
    },
  }
}

function buildLoginRequest(): PopupRequest {
  const clientId = (import.meta.env.VITE_MSAL_CLIENT_ID ?? '') as string
  const explicitScope = (import.meta.env.VITE_MSAL_API_SCOPE ?? '') as string
  const scope = explicitScope.trim() || (clientId ? `api://${clientId}/.default` : '')
  return {
    scopes: scope ? [scope] : [],
    prompt: 'select_account',
  }
}

/**
 * Whether the commercial mode env is fully populated. The sign-in
 * page consults this to disable the button (and surface a clear
 * banner) when the operator forgot to set tenant / client.
 */
export function isMsalConfigured(): boolean {
  const tenantId = (import.meta.env.VITE_MSAL_TENANT_ID ?? '') as string
  const clientId = (import.meta.env.VITE_MSAL_CLIENT_ID ?? '') as string
  return Boolean(tenantId.trim() && clientId.trim())
}

export const loginRequest: PopupRequest = buildLoginRequest()

/**
 * Initialize MSAL and the same-origin token bridge. Returns the
 * `PublicClientApplication` so `main.tsx` can pass it to
 * `<MsalProvider instance={...}>`.
 */
export async function bootstrapMsal(): Promise<PublicClientApplication> {
  const instance = new PublicClientApplication(buildMsalConfig())

  // Keep the active account in sync with login / acquire / SSO events
  // so `useAccount`, `getActiveAccount`, and the fetch bridge all see
  // the same principal without each consumer having to opt in.
  instance.addEventCallback((event) => {
    if (
      (event.eventType === EventType.LOGIN_SUCCESS ||
        event.eventType === EventType.ACQUIRE_TOKEN_SUCCESS ||
        event.eventType === EventType.SSO_SILENT_SUCCESS) &&
      event.payload
    ) {
      const result = event.payload as AuthenticationResult
      if (result.account) {
        instance.setActiveAccount(result.account)
      }
    }
    if (event.eventType === EventType.LOGOUT_SUCCESS) {
      instance.setActiveAccount(null)
    }
  })

  await instance.initialize()

  try {
    const response = await instance.handleRedirectPromise()
    if (response?.account) {
      instance.setActiveAccount(response.account)
    } else {
      const accounts = instance.getAllAccounts()
      if (accounts.length > 0 && !instance.getActiveAccount()) {
        instance.setActiveAccount(accounts[0])
      }
    }
  } catch (err) {
    console.error('handleRedirectPromise failed', err)
  }

  installFetchBridge(instance)
  return instance
}
