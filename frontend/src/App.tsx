import { lazy, type ReactNode, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ChatPage } from './pages/ChatPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PopupPage } from './pages/PopupPage'
import { SidebarPage } from './pages/SidebarPage'

// CTR-0091 (PRP-0050): commercial mode is opt-in via build flag.
// When `VITE_AUTH_PROVIDER === 'msal'`, the OSS bundle gates the
// chat surfaces behind an MSAL `<AuthGate>` and exposes a `/signin`
// route. Both modules are dynamic-imported so the OSS-default build
// (flag unset) does not pull MSAL packages into the bundle.
const COMMERCIAL_MODE = import.meta.env.VITE_AUTH_PROVIDER === 'msal'

const SignInPage = COMMERCIAL_MODE
  ? lazy(() => import('./pages/SignInPage').then((m) => ({ default: m.SignInPage })))
  : null

const AuthGate = COMMERCIAL_MODE ? lazy(() => import('./auth/auth-gate').then((m) => ({ default: m.AuthGate }))) : null

function maybeGated(children: ReactNode) {
  if (COMMERCIAL_MODE && AuthGate) {
    return <AuthGate>{children}</AuthGate>
  }
  return children
}

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={maybeGated(<ChatPage />)} />
          <Route path="/popup" element={maybeGated(<PopupPage />)} />
          <Route path="/sidebar" element={maybeGated(<SidebarPage />)} />
          {COMMERCIAL_MODE && SignInPage ? <Route path="/signin" element={<SignInPage />} /> : null}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
