import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Preview, ProfileSpec } from '../../lib/api'
import { makePreview, makeSpec } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { PreviewPanel } from './PreviewPanel'

type PreviewRequest = { profile: ProfileSpec; period_days: number }

/** Answer every preview with `answer`; the requests are kept in order. */
function servePreview(
  answer: (request: PreviewRequest) => Preview | Promise<Preview> = () => makePreview(),
) {
  const asked: PreviewRequest[] = []
  server.use(
    http.post(apiUrl('/selection/preview'), async ({ request }) => {
      const body = (await request.json()) as PreviewRequest
      asked.push(body)
      return HttpResponse.json(await answer(body))
    }),
  )
  return asked
}

describe('PreviewPanel', () => {
  it('says when only full-text search could pick the publications', async () => {
    servePreview(() => makePreview({ lexical_only: true }))
    const spec = makeSpec()
    renderWithProviders(<PreviewPanel draft={spec} saved={spec} isDirty={false} />)

    expect(
      await screen.findByText(
        'Поиск: без модели (n-граммы) · векторный поиск недоступен, работает только полнотекстовый',
      ),
    ).toBeInTheDocument()
  })
})
