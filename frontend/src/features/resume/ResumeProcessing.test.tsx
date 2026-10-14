import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResumeProcessing } from './ResumeProcessing'

describe('ResumeProcessing', () => {
  it('promises a few seconds without the model and up to half a minute with it', () => {
    const { rerender } = render(<ResumeProcessing usesModel={false} usesDocling={false} />)
    expect(screen.getByRole('status', { name: 'Читаем резюме' })).toBeInTheDocument()
    expect(
      screen.getByText(/^Извлекаем текст,.*Без модели обработка занимает несколько секунд\.$/),
    ).toBeInTheDocument()

    rerender(<ResumeProcessing usesModel usesDocling />)
    expect(
      screen.getByText(
        /^Разбираем структуру документа,.*С языковой моделью это занимает 10–30 секунд\.$/,
      ),
    ).toBeInTheDocument()
  })
})
