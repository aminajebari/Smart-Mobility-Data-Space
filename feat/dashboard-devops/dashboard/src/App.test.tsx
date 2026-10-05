import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('dashboard smoke test', () => {
  it('renders the main dashboard widgets from mock data', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Mobility Overview' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Network traffic & congestion' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /congestion from 8 to 9:30/i })).toBeInTheDocument()
    expect(screen.getByText('Tunis Bus Network')).toBeInTheDocument()
    expect(screen.getByText('Congestion probability')).toBeInTheDocument()
    expect(screen.getByText('Road flow telemetry')).toBeInTheDocument()
  })
})
