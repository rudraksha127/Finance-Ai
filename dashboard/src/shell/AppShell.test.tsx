/**
 * App shell tests: RESEARCH MODE indicator persistence (§6.2), navigation
 * presence (§5.2), and footer disclaimer.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'
import { api } from '../api/client'

vi.mock('../api/client', () => ({
  api: {
    version: vi.fn(),
    health: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

beforeEach(() => {
  mockedApi.version.mockResolvedValue({
    api_version: 'v1',
    model_version: 'random_forest_v0.2',
    feature_version: 'v0.2',
    label_version: 'v0.2',
    strategy_version: 'stg_v0.1',
    mode: 'research',
  })
  mockedApi.health.mockResolvedValue({
    status: 'ok',
    model_loaded: true,
    model_version: 'random_forest_v0.2',
    uptime_seconds: 10,
    mode: 'research',
  })
})

function renderShell() {
  return render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  it('always shows the RESEARCH MODE badge (§6.2)', async () => {
    renderShell()
    expect(screen.getByText('RESEARCH MODE')).toBeInTheDocument()
  })

  it('renders all eight navigation items (§5.2)', () => {
    renderShell()
    for (const label of [
      'Overview',
      'Market Explorer',
      'Predictions',
      'Backtests',
      'Experiments',
      'Models',
      'Datasets',
      'System Health',
    ]) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('shows the research disclaimer in the footer (§3.2)', () => {
    renderShell()
    expect(screen.getByText(/research & simulation only/i)).toBeInTheDocument()
    expect(screen.getByText(/cannot place orders/i)).toBeInTheDocument()
  })

  it('shows the active model version linked to the Models page', async () => {
    renderShell()
    const link = await screen.findByRole('link', { name: /random_forest_v0\.2 · stg_v0\.1/ })
    expect(link).toHaveAttribute('href', '/models')
  })

  it('never renders a LIVE mode badge (§6.2 rule)', () => {
    renderShell()
    expect(screen.queryByText(/LIVE MODE/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/LIVE TRADING/i)).not.toBeInTheDocument()
  })
})
