import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeSummary } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { DigestHeading } from './DigestHeading'

// Both readings carry a short and a full label (one is hidden by CSS on a
// phone), so a name reads "ИнженерИнженер" in jsdom.
const switcher = () => screen.getByRole('radiogroup', { name: 'Для кого читать выпуск' })
const reading = (name: RegExp) => within(switcher()).getByRole('radio', { name })

describe('DigestHeading', () => {
  it('names the profile, its version and the period above the issue’s title', () => {
    renderWithProviders(<DigestHeading summary={makeSummary({ profile_version: 3 })} />)
    expect(screen.getByText('Инженер АСУ ТП · версия 3 · 12 окт. – 13 окт.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Выпуск за сутки' })).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup')).toBeNull()
  })

  it('calls an issue without a title by its profile', () => {
    renderWithProviders(<DigestHeading summary={makeSummary({ title: null })} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Инженер АСУ ТП' })).toBeInTheDocument()
  })

  it('opens the manager’s issue of the same build from the engineer’s', async () => {
    const onOpen = vi.fn()
    const twin = makeSummary({ id: 'digest-2', audience: 'management' })
    // An issue from before audiences existed reads as the engineer's.
    const { user } = renderWithProviders(
      <DigestHeading summary={makeSummary({ audience: undefined })} twin={twin} onOpen={onOpen} />,
    )
    expect(screen.getByText('те же новости, другой язык')).toBeInTheDocument()
    expect(reading(/Инженер/)).toBeChecked()

    await user.click(reading(/Инженер/))
    expect(onOpen).not.toHaveBeenCalled()

    await user.click(reading(/Руководитель/))
    expect(onOpen).toHaveBeenCalledWith('digest-2')
  })

  it('opens the engineer’s issue of the same build from the manager’s', async () => {
    const onOpen = vi.fn()
    const twin = makeSummary({ id: 'digest-1', audience: 'specialist' })
    const { user } = renderWithProviders(
      <DigestHeading
        summary={makeSummary({ id: 'digest-2', audience: 'management' })}
        twin={twin}
        onOpen={onOpen}
      />,
    )
    expect(reading(/Руководитель/)).toBeChecked()

    await user.click(reading(/Инженер/))
    expect(onOpen).toHaveBeenCalledWith('digest-1')
  })
})
