import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

interface MediaRowProps {
  title: string
  children: ReactNode
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (2 - 2 * t) ** 3 / 2
}

export function MediaRow({ title, children }: MediaRowProps) {
  const scrollerRef = useRef<HTMLDivElement>(null)
  const animRef = useRef(0)
  const [canLeft, setCanLeft] = useState(false)
  const [canRight, setCanRight] = useState(false)

  const updateArrows = useCallback(() => {
    const el = scrollerRef.current
    if (!el) return
    const maxScroll = el.scrollWidth - el.clientWidth
    setCanLeft(el.scrollLeft > 4)
    setCanRight(maxScroll > 4 && el.scrollLeft < maxScroll - 4)
  }, [])

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return

    updateArrows()
    el.addEventListener('scroll', updateArrows, { passive: true })
    window.addEventListener('resize', updateArrows)
    const ro = new ResizeObserver(updateArrows)
    ro.observe(el)

    return () => {
      el.removeEventListener('scroll', updateArrows)
      window.removeEventListener('resize', updateArrows)
      ro.disconnect()
    }
  }, [updateArrows, children])

  useEffect(() => {
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [])

  function scrollByDir(dir: -1 | 1) {
    const el = scrollerRef.current
    if (!el) return

    const amount = Math.max(el.clientWidth * 0.85, 280)
    const start = el.scrollLeft
    const maxScroll = Math.max(0, el.scrollWidth - el.clientWidth)
    const target = Math.max(0, Math.min(maxScroll, start + dir * amount))
    const distance = target - start
    if (Math.abs(distance) < 1) return

    if (animRef.current) cancelAnimationFrame(animRef.current)

    const durationMs = 520
    const startedAt = performance.now()

    const step = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / durationMs)
      el.scrollLeft = start + distance * easeInOutCubic(progress)
      if (progress < 1) {
        animRef.current = requestAnimationFrame(step)
        return
      }
      el.scrollLeft = target
      animRef.current = 0
      updateArrows()
    }

    animRef.current = requestAnimationFrame(step)
  }

  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">{title}</h2>
        <div className="carousel-arrows">
          <button
            type="button"
            className="carousel-arrow"
            aria-label={`Scroll ${title} left`}
            disabled={!canLeft}
            onClick={() => scrollByDir(-1)}
          >
            ‹
          </button>
          <button
            type="button"
            className="carousel-arrow"
            aria-label={`Scroll ${title} right`}
            disabled={!canRight}
            onClick={() => scrollByDir(1)}
          >
            ›
          </button>
        </div>
      </div>
      <div className="row-shell">
        <div className="row" ref={scrollerRef}>
          {children}
        </div>
      </div>
    </section>
  )
}
