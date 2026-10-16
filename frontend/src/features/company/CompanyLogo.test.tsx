import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { companyInitials } from '../../lib/company'
import { keys } from '../../lib/queries'
import { ChannelsPage } from '../../pages/ChannelsPage'
import { CompanyPage } from '../../pages/CompanyPage'
import { makeCompany, makeMe } from '../../test/fixtures'
import { createTestQueryClient, renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'

const MEMBER = makeMe({
  company: {
    company: 'АО «Энергосеть»',
    team: 'SOC',
    role: 'member',
    job_title: 'инженер SOC',
    manager: 'Ирина Волкова',
  },
})

function renderAs(ui: React.ReactElement, me = makeMe()) {
  const client = createTestQueryClient()
  client.setQueryData(keys.me, me)
  return renderWithProviders(ui, { client })
}

describe('company logo', () => {
  it('names a company by its letters without its legal form', () => {
    expect(companyInitials('АО «Энергосеть»')).toBe('ЭН')
    expect(companyInitials('ООО Северные сети')).toBe('СС')
    expect(companyInitials('Росатом')).toBe('РО')
  })

  it('uploads a logo from the company dialog and takes it away again', async () => {
    let logo: string | null = null
    let uploaded: string | null = null
    server.use(
      http.get(apiUrl('/company'), () => HttpResponse.json(makeCompany({ logo_url: logo }))),
      http.put(apiUrl('/company/logo'), async ({ request }) => {
        uploaded = request.headers.get('content-type')
        logo = '/api/v1/company/logo?v=1'
        return HttpResponse.json(makeCompany({ logo_url: logo }))
      }),
      http.delete(apiUrl('/company/logo'), () => {
        logo = null
        return HttpResponse.json(makeCompany())
      }),
    )
    const { user } = renderAs(<CompanyPage />)

    await user.click(await screen.findByRole('button', { name: 'О компании' }))
    const dialog = await screen.findByRole('dialog')
    const file = new File([new Uint8Array([137, 80, 78, 71])], 'logo.png', { type: 'image/png' })
    await user.upload(within(dialog).getByLabelText('Файл логотипа'), file)

    expect(
      await within(dialog).findByRole('button', { name: 'Заменить логотип' }),
    ).toBeInTheDocument()
    expect(uploaded).toBe('image/png')
    await user.click(within(dialog).getByRole('button', { name: 'Убрать' }))
    expect(
      await within(dialog).findByRole('button', { name: 'Загрузить логотип' }),
    ).toBeInTheDocument()
  })
})

describe('what a person a company added sees', () => {
  it('reads that the space and its channels are the manager’s, and asks the server nothing', async () => {
    const asked: string[] = []
    server.use(
      http.get(apiUrl('/company'), () => {
        asked.push('company')
        return HttpResponse.json(null)
      }),
      http.get(apiUrl('/publishing/channels'), () => {
        asked.push('channels')
        return HttpResponse.json([])
      }),
    )
    const { unmount } = renderAs(<CompanyPage />, MEMBER)
    expect(await screen.findByText('Вы в команде «SOC»')).toBeInTheDocument()
    expect(screen.getByText(/управляет Ирина Волкова/)).toBeInTheDocument()
    unmount()

    renderAs(<ChannelsPage />, MEMBER)
    expect(await screen.findByText('Каналы ведёт руководитель пространства')).toBeInTheDocument()
    await waitFor(() => expect(asked).toEqual([]))
  })
})
