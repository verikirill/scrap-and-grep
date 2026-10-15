import type { CSSProperties } from 'react'
import { cn } from '../lib/utils'

/** The scene the parts were cut from, in pixels. */
const SCENE = { width: 640, height: 660 }

type Box = { x: number; y: number; w: number; h: number }

/** Where a part sits in the scene, as percentages of the scaled box. */
function place({ x, y, w, h }: Box): CSSProperties {
  return {
    left: `${(x / SCENE.width) * 100}%`,
    top: `${(y / SCENE.height) * 100}%`,
    width: `${(w / SCENE.width) * 100}%`,
    height: `${(h / SCENE.height) * 100}%`,
  }
}

function Part({ name, box, className }: { name: string; box: Box; className?: string }) {
  return (
    <img
      src={`/brand/cat/${name}.webp`}
      alt=""
      aria-hidden
      draggable={false}
      decoding="async"
      className={className}
      style={place(box)}
    />
  )
}

export type BrandCatPose = 'search' | 'sleep'

/**
 * The cat from the logo, put together from its parts so that they can move:
 * searching, it sways its tail, tilts its head, blinks and glides the
 * magnifier over the paper; asleep, it only breathes. Decorative: the text
 * next to it says what happened. Without motion under "reduce motion".
 */
export function BrandCat({
  size = 200,
  pose = 'search',
  className,
}: {
  /** Width in pixels; the height follows the scene. */
  size?: number
  pose?: BrandCatPose
  className?: string
}) {
  const isAsleep = pose === 'sleep'
  return (
    <div
      aria-hidden
      data-pose={pose}
      className={cn('brand-cat', className)}
      style={{ width: size }}
    >
      <div className="brand-cat__group brand-cat__breath">
        <Part name="tail" box={{ x: 0, y: 300, w: 217, h: 278 }} className="brand-cat__tail" />
        <Part name="body" box={{ x: 70, y: 240, w: 344, h: 374 }} />
        <div className="brand-cat__group brand-cat__head">
          <Part name="ear-left" box={{ x: 170, y: 0, w: 111, h: 130 }} className="brand-cat__ear" />
          <Part name="ear-right" box={{ x: 345, y: 28, w: 111, h: 129 }} />
          <Part name="head" box={{ x: 150, y: 60, w: 296, h: 237 }} />
          {!isAsleep && (
            <>
              <Part
                name="eye-left"
                box={{ x: 235, y: 135, w: 103, h: 75 }}
                className="brand-cat__eye-open"
              />
              <Part
                name="eye-right"
                box={{ x: 345, y: 150, w: 94, h: 74 }}
                className="brand-cat__eye-open"
              />
            </>
          )}
          <Part
            name="eye-left-closed"
            box={{ x: 241, y: 156, w: 91, h: 32 }}
            className="brand-cat__eye-closed"
          />
          <Part
            name="eye-right-closed"
            box={{ x: 343, y: 169, w: 98, h: 36 }}
            className="brand-cat__eye-closed"
          />
        </div>
        <Part name="paper" box={{ x: 170, y: 290, w: 324, h: 288 }} />
        {/* The magnifier glides on two axes out of step: a slow oval. */}
        <div className="brand-cat__group brand-cat__glass-x">
          <div className="brand-cat__group brand-cat__glass-y">
            <span className="brand-cat__lens" style={place({ x: 407, y: 430, w: 150, h: 150 })} />
            <Part name="glass" box={{ x: 385, y: 410, w: 227, h: 236 }} />
          </div>
        </div>
      </div>
    </div>
  )
}
