import type { PointerEvent } from 'react'

/**
 * Material ripple: a circle that grows from the point of the press. The element
 * needs `position: relative` and `overflow: hidden` (buttonClass gives both).
 * Skipped for users who asked the system to reduce motion.
 */
export function ripple(event: PointerEvent<HTMLElement>): void {
  if (event.button !== 0 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const target = event.currentTarget
  const box = target.getBoundingClientRect()
  const size = Math.hypot(box.width, box.height) * 2
  const wave = document.createElement('span')
  wave.className = 'ripple'
  wave.style.width = wave.style.height = `${size}px`
  wave.style.left = `${event.clientX - box.left - size / 2}px`
  wave.style.top = `${event.clientY - box.top - size / 2}px`
  target.appendChild(wave)
  wave.addEventListener('animationend', () => wave.remove(), { once: true })
}
