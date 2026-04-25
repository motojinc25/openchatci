/**
 * Branding Overlay (CTR-0091, PRP-0050).
 *
 * Reads `VITE_BRAND_*` env vars at build time and falls back to OSS
 * defaults so a vanilla OSS build never references a commercial
 * brand. Commercial deployments override the values via env to
 * paint the sign-in landing page (and any future shell surfaces)
 * with their product name and color palette.
 */

function envString(key: string, fallback: string): string {
  const value = (import.meta.env[key] ?? '') as string
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : fallback
}

export const brand = {
  productName: envString('VITE_BRAND_PRODUCT_NAME', 'OpenChatCi'),
  tagline: envString('VITE_BRAND_TAGLINE', ''),
  primaryColor: envString('VITE_BRAND_PRIMARY_COLOR', '#0b5ed7'),
  accentColor: envString('VITE_BRAND_ACCENT_COLOR', '#6c2bd9'),
} as const

export type Brand = typeof brand
