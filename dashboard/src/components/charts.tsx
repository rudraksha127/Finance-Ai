/**
 * ECharts wrappers (UI_UX_BLUEPRINT §32.2: one charting library).
 * Charts plot backend-authoritative series only (§29.1) and always pair
 * with accessible summaries (§27). Axis transformations that would distort
 * values are avoided (§11).
 */
import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, CandlestickChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Candle } from '../api/types'

echarts.use([
  LineChart,
  BarChart,
  CandlestickChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
])

function useChart(option: echarts.EChartsCoreOption, deps: unknown[]) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    chartRef.current = echarts.init(ref.current)
    const observer = new ResizeObserver(() => chartRef.current?.resize())
    observer.observe(ref.current)
    return () => {
      observer.disconnect()
      chartRef.current?.dispose()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}

const AXIS_STYLE = {
  axisLine: { lineStyle: { color: '#c3c9d1' } },
  axisLabel: { color: '#5a6472', fontSize: 11 },
  splitLine: { lineStyle: { color: '#eceff2' } },
}

interface EquityChartProps {
  points: Array<{ timestamp: string; equity: number }>
  benchmark?: Array<{ timestamp: string; equity: number }>
}

/** Equity curve, normalized to the $1.00 basis (§30.2, EVAL §16.1). */
export function EquityChart({ points, benchmark }: EquityChartProps) {
  const ref = useChart(
    {
      grid: { left: 56, right: 16, top: 28, bottom: 42 },
      legend: benchmark ? { data: ['Strategy', 'Buy & Hold'], top: 0, textStyle: { fontSize: 11 } } : undefined,
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: points.map((p) => p.timestamp.slice(0, 10)),
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', scale: true, name: 'Equity ($1.00 basis)', ...AXIS_STYLE },
      dataZoom: [{ type: 'inside' }],
      series: [
        {
          name: 'Strategy',
          type: 'line',
          data: points.map((p) => p.equity),
          showSymbol: false,
          lineStyle: { color: '#1f5f8b', width: 1.5 },
        },
        ...(benchmark
          ? [
              {
                name: 'Buy & Hold',
                type: 'line' as const,
                data: benchmark.map((p) => p.equity),
                showSymbol: false,
                lineStyle: { color: '#8a929e', width: 1.2, type: 'dashed' as const },
              },
            ]
          : []),
      ],
    },
    [points, benchmark],
  )
  return (
    <div>
      <div ref={ref} style={{ height: 280 }} role="img" aria-label="Equity curve chart of the strategy cumulative performance versus benchmark" />
      <p className="muted" style={{ fontSize: 'var(--text-xs)', margin: '4px 0 0' }}>
        Hypothetical $1.00 basis · simulated historical performance, net of costs.
      </p>
    </div>
  )
}

interface DrawdownChartProps {
  points: Array<{ timestamp: string; drawdown: number }>
}

/** Drawdown curve (negative values below running peak). */
export function DrawdownChart({ points }: DrawdownChartProps) {
  const ref = useChart(
    {
      grid: { left: 56, right: 16, top: 16, bottom: 42 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: points.map((p) => p.timestamp.slice(0, 10)),
        ...AXIS_STYLE,
      },
      yAxis: { type: 'value', name: 'Drawdown', ...AXIS_STYLE },
      dataZoom: [{ type: 'inside' }],
      series: [
        {
          type: 'line',
          data: points.map((p) => p.drawdown),
          showSymbol: false,
          areaStyle: { color: 'rgba(179, 55, 46, 0.15)' },
          lineStyle: { color: '#b3372e', width: 1.2 },
        },
      ],
    },
    [points],
  )
  return (
    <div>
      <div ref={ref} style={{ height: 200 }} role="img" aria-label="Drawdown chart showing percentage decline from running equity peak" />
    </div>
  )
}

interface PriceChartProps {
  candles: Candle[]
  stale: boolean
}

/** Price + volume (§10 Market Explorer). No invented values (§11). */
export function PriceChart({ candles, stale }: PriceChartProps) {
  const categories = candles.map((c) => c.timestamp.slice(0, 10))
  const maxVolume = Math.max(...candles.map((c) => c.volume), 1)
  const ref = useChart(
    {
      grid: [
        { left: 56, right: 16, top: 24, bottom: 110 },
        { left: 56, right: 16, top: '68%', bottom: 42 },
      ],
      tooltip: { trigger: 'axis' },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      xAxis: [
        { type: 'category', data: categories, gridIndex: 0, ...AXIS_STYLE },
        { type: 'category', data: categories, gridIndex: 1, ...AXIS_STYLE },
      ],
      yAxis: [
        { type: 'value', scale: true, name: 'Close', gridIndex: 0, ...AXIS_STYLE },
        { type: 'value', gridIndex: 1, ...AXIS_STYLE },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
      series: [
        {
          name: 'Close',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: candles.map((c) => c.close),
          showSymbol: false,
          lineStyle: { color: '#1d2530', width: 1.2 },
        },
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: candles.map((c) => c.volume / maxVolume),
          itemStyle: { color: '#a9b2bd' },
        },
      ],
    },
    [candles],
  )
  return (
    <div>
      {stale && (
        <p className="muted" style={{ fontSize: 'var(--text-xs)', margin: '0 0 4px' }}>
          STALE DATA — last candle {candles.length ? candles[candles.length - 1].timestamp.slice(0, 10) : 'unknown'}
        </p>
      )}
      <div ref={ref} style={{ height: 360 }} role="img" aria-label={`Price and volume chart for ${candles.length} daily candles`} />
    </div>
  )
}
