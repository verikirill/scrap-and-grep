import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

function Settings({ label }: { label?: string }) {
  return (
    <Tabs defaultValue="time">
      <TabsList aria-label={label}>
        <TabsTrigger value="time">Время</TabsTrigger>
        <TabsTrigger value="look">Вид</TabsTrigger>
      </TabsList>
      <TabsContent value="time">Публиковать в 09:00</TabsContent>
      <TabsContent value="look">Подпись под медиа</TabsContent>
    </Tabs>
  )
}

describe('Tabs', () => {
  it('opens on the default tab and switches panels on a choice', async () => {
    const user = userEvent.setup()
    render(<Settings label="Настройки канала" />)
    expect(screen.getByRole('tablist', { name: 'Настройки канала' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Время' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Публиковать в 09:00')

    await user.click(screen.getByRole('tab', { name: 'Вид' }))

    expect(screen.getByRole('tab', { name: 'Вид' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Подпись под медиа')
  })

  it('moves between tabs with the arrow keys', async () => {
    const user = userEvent.setup()
    render(<Settings label="Настройки канала" />)
    await user.tab()
    expect(screen.getByRole('tab', { name: 'Время' })).toHaveFocus()

    await user.keyboard('{ArrowRight}')

    expect(screen.getByRole('tab', { name: 'Вид' })).toHaveAttribute('aria-selected', 'true')
  })

  it('names an unnamed list «Разделы»', () => {
    render(<Settings />)
    expect(screen.getByRole('tablist', { name: 'Разделы' })).toBeInTheDocument()
  })
})
