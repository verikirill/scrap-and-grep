import { Audio } from '@remotion/media'
import { AbsoluteFill, Sequence, useVideoConfig } from 'remotion'
import { BeatScene } from './scenes/BeatScene'
import { Background } from './scenes/Background'
import { Captions } from './scenes/Captions'
import { Header } from './scenes/Header'
import { HookScene } from './scenes/HookScene'
import { OutroScene } from './scenes/OutroScene'
import type { ShortProps } from './types'

const toFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps)

/**
 * The whole short: background, the hook, one scene per news item, the outro,
 * story-style progress on top and karaoke captions below. Scene boundaries
 * come from the narration timeline, so pictures change when the voice does.
 */
export function DigestShort(props: ShortProps) {
  const { fps, durationInFrames } = useVideoConfig()
  const hookFrames = Math.max(1, toFrames(props.hookEndMs, fps))
  const outroFrom = toFrames(props.outroStartMs, fps)

  return (
    <AbsoluteFill>
      <Background />
      <Sequence durationInFrames={hookFrames} name="Hook">
        <HookScene hook={props.hook} audience={props.audience} beats={props.beats} durationInFrames={hookFrames} />
      </Sequence>
      {props.beats.map((beat, index) => {
        const from = toFrames(beat.startMs, fps)
        const duration = Math.max(1, toFrames(beat.endMs, fps) - from)
        return (
          <Sequence key={index} from={from} durationInFrames={duration} name={`Beat ${index + 1}`}>
            <BeatScene beat={beat} number={index + 1} durationInFrames={duration} />
          </Sequence>
        )
      })}
      <Sequence from={outroFrom} durationInFrames={Math.max(1, durationInFrames - outroFrom)} name="Outro">
        <OutroScene brand={props.brand} outro={props.outro} />
      </Sequence>
      <Header brand={props.brand} period={props.period} beats={props.beats} />
      <Captions words={props.words} />
      {props.audioSrc && <Audio src={props.audioSrc} />}
    </AbsoluteFill>
  )
}
