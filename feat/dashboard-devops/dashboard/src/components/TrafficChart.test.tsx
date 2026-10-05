import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TrafficChart, congestionRanges } from './TrafficChart'

const point = (time: string, incident = false) => ({ time, density: 50, speed: 30, incident })

describe('TrafficChart', () => {
  it('groups consecutive congested points into ranges', () => {
    const data = [point('a'), point('b', true), point('c', true), point('d'), point('e', true)]
    expect(congestionRanges(data)).toEqual([[1, 2], [4, 4]])
  })

  it('labels the congestion window from live data', () => {
    render(<TrafficChart data={[point('10:00:00'), point('10:00:20', true), point('10:00:40', true)]} />)
    expect(screen.getByRole('img', { name: /congestion from 10:00:20 to 10:00:40/i })).toBeInTheDocument()
  })

  it('handles empty data', () => {
    render(<TrafficChart data={[]} />)
    expect(screen.getByText(/waiting for traffic sensor data/i)).toBeInTheDocument()
  })
})
