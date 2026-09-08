/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional explicit API base URL (defaults to same-origin /api proxy). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
