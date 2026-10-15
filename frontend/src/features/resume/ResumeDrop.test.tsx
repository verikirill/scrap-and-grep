import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeMeta } from '../../test/fixtures'
import { ResumeDrop } from './ResumeDrop'

const file = (name: string, bytes = 1_000) => new File([new Uint8Array(bytes)], name)

/** The file field behind the drop zone, which the zone's button opens. */
const fileInput = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement

describe('ResumeDrop', () => {
  it('takes a dropped resume in a format the server reads', () => {
    const onFile = vi.fn()
    render(<ResumeDrop meta={makeMeta()} isBusy={false} onFile={onFile} />)
    const resume = file('Резюме Петровой.PDF')

    fireEvent.drop(screen.getByRole('button', { name: /Перетащите резюме сюда/ }), {
      dataTransfer: { files: [resume] },
    })

    expect(onFile).toHaveBeenCalledWith(resume)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('offers only the formats the server reads, and refuses another before uploading', async () => {
    const onFile = vi.fn()
    const user = userEvent.setup({ applyAccept: false })
    const { container } = render(
      <ResumeDrop
        meta={makeMeta({ resume_formats: ['pdf', 'docx', 'html'] })}
        isBusy={false}
        onFile={onFile}
      />,
    )
    expect(fileInput(container)).toHaveAttribute('accept', '.pdf,.docx,.html,.htm')
    expect(screen.getByText('PDF, DOCX, HTML · до 8 МБ')).toBeInTheDocument()

    await user.upload(fileInput(container), file('resume.txt'))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Неподдерживаемый формат файла. Подходят: PDF, DOCX, HTML.',
    )
    expect(onFile).not.toHaveBeenCalled()

    // A good file after a bad one clears the complaint.
    await user.upload(fileInput(container), file('resume.htm'))
    expect(onFile).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('refuses a file over the server limit before uploading it', () => {
    const onFile = vi.fn()
    render(
      <ResumeDrop
        meta={makeMeta({ resume_max_bytes: 2_000_000 })}
        isBusy={false}
        onFile={onFile}
      />,
    )

    fireEvent.drop(screen.getByRole('button', { name: /Перетащите резюме сюда/ }), {
      dataTransfer: { files: [file('resume.pdf', 2_000_001)] },
    })

    expect(screen.getByRole('alert')).toHaveTextContent('Размер файла превышает 2 МБ.')
    expect(onFile).not.toHaveBeenCalled()
  })

  it('ignores a file dropped while the previous one is uploading', () => {
    const onFile = vi.fn()
    render(<ResumeDrop meta={makeMeta()} isBusy onFile={onFile} />)

    const zone = screen.getByRole('button', { name: /Перетащите резюме сюда/ })
    expect(zone).toBeDisabled()
    fireEvent.drop(zone, { dataTransfer: { files: [file('resume.pdf')] } })

    expect(onFile).not.toHaveBeenCalled()
  })

  it('promises recognition of scans only when the server can read them', () => {
    const { rerender } = render(
      <ResumeDrop meta={makeMeta({ resume_parser: 'builtin' })} isBusy={false} onFile={vi.fn()} />,
    )
    expect(screen.queryByText(/Сканы и фото страниц/)).toBeNull()

    rerender(
      <ResumeDrop meta={makeMeta({ resume_parser: 'docling' })} isBusy={false} onFile={vi.fn()} />,
    )
    expect(screen.getByText(/Сканы и фото страниц тоже подойдут/)).toBeInTheDocument()
  })

  it('shrinks to one row for replacing a resume already read', () => {
    const onFile = vi.fn()
    render(<ResumeDrop meta={makeMeta()} isBusy={false} onFile={onFile} isCompact />)

    const row = screen.getByRole('button', { name: /Заменить резюме/ })
    expect(screen.queryByText('Перетащите резюме сюда')).toBeNull()
    fireEvent.drop(row, { dataTransfer: { files: [file('new.docx')] } })

    expect(onFile).toHaveBeenCalledTimes(1)
  })
})
