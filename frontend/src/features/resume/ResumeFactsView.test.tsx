import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeResume, makeResumeFacts } from '../../test/fixtures'
import { ResumeFactsView } from './ResumeFactsView'

describe('ResumeFactsView', () => {
  it('says how the resume was read, and leaves out the level and summary it lacks', () => {
    const facts = makeResumeFacts({ seniority: 'unknown', summary: '', by_model: false })
    render(
      <ResumeFactsView
        resume={makeResume({ file_format: 'docx', parser: 'docling' })}
        facts={facts}
      />,
    )

    expect(
      screen.getByText('DOCX · docling · разобрано по таблице направлений'),
    ).toBeInTheDocument()
    expect(screen.getByText(facts.headline)).toBeInTheDocument()
    expect(screen.queryByText(/специалист|руководитель/)).toBeNull()
    expect(screen.queryByText(/Восемь лет/)).toBeNull()
  })

  it('shows every skill when no limit is asked', () => {
    const skills = Array.from({ length: 20 }, (_, index) => `Навык ${index + 1}`)
    render(<ResumeFactsView resume={makeResume()} facts={makeResumeFacts({ skills })} />)

    expect(screen.getByText('Навык 20')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
