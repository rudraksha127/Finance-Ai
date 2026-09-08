import '@testing-library/jest-dom/vitest'

// jsdom lacks ResizeObserver (used by the ECharts wrappers); provide a
// minimal stub so chart components mount in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
}

// jsdom has no canvas 2D context (ECharts renders via <canvas>); provide a
// permissive no-op stub so chart init succeeds and the accessible chart
// summaries remain testable.
const canvasCtxStub = new Proxy(
  {},
  {
    get: (_target, prop) => {
      if (prop === 'canvas') return { width: 0, height: 0 }
      if (prop === 'measureText') return () => ({ width: 0 })
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient') {
        return () => ({ addColorStop: () => {} })
      }
      return () => undefined
    },
  },
)
HTMLCanvasElement.prototype.getContext = (() => canvasCtxStub) as unknown as typeof HTMLCanvasElement.prototype.getContext
