import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppShell } from './shell/AppShell'
import { LoadingState } from './components/States'
import './styles/global.css'

// Route-level code splitting (§33.2): heavy pages load on demand.
const Overview = lazy(() => import('./pages/Overview'))
const MarketExplorer = lazy(() => import('./pages/MarketExplorer'))
const Predictions = lazy(() => import('./pages/Predictions'))
const Backtests = lazy(() => import('./pages/Backtests'))
const Experiments = lazy(() => import('./pages/Experiments'))
const Models = lazy(() => import('./pages/Models'))
const Datasets = lazy(() => import('./pages/Datasets'))
const SystemHealth = lazy(() => import('./pages/SystemHealth'))

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'market', element: <MarketExplorer /> },
      { path: 'predictions', element: <Predictions /> },
      { path: 'backtests', element: <Backtests /> },
      { path: 'experiments', element: <Experiments /> },
      { path: 'models', element: <Models /> },
      { path: 'datasets', element: <Datasets /> },
      { path: 'system', element: <SystemHealth /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider
      router={router}
      fallbackElement={<LoadingState label="Starting dashboard…" />}
    />
  </StrictMode>,
)

// Keep Suspense available for lazy chunks inside routes.
export const RouteSuspense = Suspense
