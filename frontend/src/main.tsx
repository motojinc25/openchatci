import { StrictMode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { App } from './App'
import './index.css'

const rootElement: HTMLElement =
  document.getElementById('root') ??
  (() => {
    throw new Error('Root element not found')
  })()

const reactRoot: Root = createRoot(rootElement)

// CTR-0091 (PRP-0050): commercial mode is opt-in via build flag.
// When `VITE_AUTH_PROVIDER === 'msal'`, dynamic-import the MSAL
// bootstrap and wrap `<App />` in `<MsalProvider>`. The default OSS
// build never resolves these imports so Vite tree-shake removes the
// MSAL packages from the production bundle.
async function bootstrap(): Promise<void> {
  if (import.meta.env.VITE_AUTH_PROVIDER === 'msal') {
    try {
      const [{ MsalProvider }, { bootstrapMsal }] = await Promise.all([
        import('@azure/msal-react'),
        import('./auth/msal-bootstrap'),
      ])
      const instance = await bootstrapMsal()
      reactRoot.render(
        <StrictMode>
          <MsalProvider instance={instance}>
            <App />
          </MsalProvider>
        </StrictMode>,
      )
      return
    } catch (err) {
      console.error('[chatci] commercial bootstrap failed; falling back to inert UI', err)
      rootElement.innerHTML = `
        <main style="padding:2rem;font-family:system-ui;color:#b00020">
          <h1>Sign-in unavailable</h1>
          <p>${err instanceof Error ? err.message : String(err)}</p>
          <p>Common causes:
            <ul>
              <li><code>VITE_MSAL_TENANT_ID</code> /
                <code>VITE_MSAL_CLIENT_ID</code> missing in the SPA env</li>
              <li>Redirect URI not registered on the Entra ID app</li>
            </ul>
          </p>
        </main>`
      return
    }
  }

  // OSS default: no auth, no MSAL imports executed.
  reactRoot.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void bootstrap()
