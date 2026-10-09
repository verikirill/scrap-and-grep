import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { toast } from '../../lib/toast'
import { Check, ContentCopy, Hub, KeyRound, Trash2 } from '../../components/icons'
import { EASE, INPUT_CLASS } from '../../components/tokens'
import { Button, Card, ErrorNote, Field } from '../../components/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'
import type { NewMcpKey } from '../../lib/api'
import { formatDateTime, formatRelative } from '../../lib/format'
import { useCreateMcpKey, useMcpKeys, useRevokeMcpKey } from '../../lib/queries'

const SERVER_NAME = 'scrap-and-grep'

function CopyButton({ text, label }: { text: string; label: string }) {
  const [isCopied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      toast.error('Не получилось скопировать, выделите текст вручную')
    }
  }
  return (
    <Button
      size="sm"
      variant="ghost"
      aria-label={label}
      icon={isCopied ? <Check size={16} /> : <ContentCopy size={16} />}
      onClick={copy}
    />
  )
}

function Snippet({ text, label }: { text: string; label: string }) {
  return (
    <div className="flex items-start gap-1 rounded-2xl bg-surface-tertiary p-1 pl-4">
      <pre className="min-w-0 flex-1 overflow-x-auto py-2.5 font-mono text-[12.5px] leading-5 whitespace-pre">
        {text}
      </pre>
      <CopyButton text={text} label={label} />
    </div>
  )
}

/** The fresh key, shown once, with ready settings for the common assistants. */
function NewKey({ created, url }: { created: NewMcpKey; url: string }) {
  const claudeCode = `claude mcp add --transport http ${SERVER_NAME} ${url} \\\n  --header "Authorization: Bearer ${created.token}"`
  // Claude Desktop reads only local servers from its config: mcp-remote bridges to ours.
  const desktop = JSON.stringify(
    {
      mcpServers: {
        [SERVER_NAME]: {
          command: 'npx',
          args: ['-y', 'mcp-remote', url, '--header', `Authorization: Bearer ${created.token}`],
        },
      },
    },
    null,
    2,
  )
  const json = JSON.stringify(
    {
      mcpServers: {
        [SERVER_NAME]: { url, headers: { Authorization: `Bearer ${created.token}` } },
      },
    },
    null,
    2,
  )
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35, ease: EASE }}
      className="flex flex-col gap-3 rounded-3xl bg-accent-soft p-5 text-accent-soft-foreground"
    >
      <p className="text-sm font-medium">
        Ключ «{created.name}» создан. Скопируйте его сейчас, посмотреть его снова будет нельзя.
      </p>
      <Snippet text={created.token} label="Скопировать ключ" />
      <Tabs defaultValue="claude">
        <TabsList aria-label="Способ подключения">
          <TabsTrigger value="claude">Claude Code</TabsTrigger>
          <TabsTrigger value="desktop">Claude Desktop</TabsTrigger>
          <TabsTrigger value="json">Cursor и другие</TabsTrigger>
        </TabsList>
        <TabsContent value="claude" className="pt-2">
          <Snippet text={claudeCode} label="Скопировать команду" />
        </TabsContent>
        <TabsContent value="desktop" className="space-y-1.5 pt-2">
          <p className="text-xs">
            Вставьте в claude_desktop_config.json и перезапустите Claude Desktop.
          </p>
          <Snippet text={desktop} label="Скопировать для claude_desktop_config.json" />
        </TabsContent>
        <TabsContent value="json" className="pt-2">
          <Snippet text={json} label="Скопировать настройки" />
        </TabsContent>
      </Tabs>
    </motion.div>
  )
}

/**
 * Keys for AI assistants: with one, Claude, Cursor or any MCP client reads
 * this reader's feed, saved articles, digests and interests, and nobody else's.
 */
export function McpAccess() {
  const keys = useMcpKeys()
  const create = useCreateMcpKey()
  const revoke = useRevokeMcpKey()
  const [name, setName] = useState('')
  const [created, setCreated] = useState<NewMcpKey | null>(null)
  const url = `${window.location.origin}/api/mcp/`

  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate(name.trim() || 'Ассистент', {
      onSuccess: (key) => {
        setCreated(key)
        setName('')
      },
    })
  }

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-default text-default-foreground">
          <Hub size={22} />
        </span>
        <div>
          <h2 className="text-base font-medium">Доступ для ИИ-ассистентов</h2>
          <p className="mt-1 text-sm text-muted">
            MCP-сервер открывает ассистенту доступ к вашей ленте, сохранённым статьям, выпускам и
            интересам. Ключ действует только для ваших данных.
          </p>
        </div>
      </div>

      <Field label="Адрес сервера" isGroup>
        <Snippet text={url} label="Скопировать адрес" />
      </Field>

      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <Field label="Новый ключ" className="min-w-0 flex-1">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={80}
            placeholder="Например, Claude на ноутбуке"
            className={INPUT_CLASS}
          />
        </Field>
        <Button
          type="submit"
          variant="tonal"
          icon={<KeyRound size={18} />}
          isBusy={create.isPending}
        >
          Создать ключ
        </Button>
      </form>
      <ErrorNote error={create.error ?? revoke.error} />

      <AnimatePresence mode="popLayout">
        {created && <NewKey key={created.id} created={created} url={url} />}
      </AnimatePresence>

      {keys.data && keys.data.length > 0 && (
        <ul className="flex flex-col divide-y divide-separator">
          <AnimatePresence initial={false}>
            {keys.data.map((key) => (
              <motion.li
                key={key.id}
                layout="position"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, ease: EASE }}
                className="flex items-center gap-3 overflow-hidden py-3"
              >
                <KeyRound size={20} className="shrink-0 text-muted" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{key.name}</p>
                  <p className="truncate text-xs text-muted">
                    <span className="font-mono">{key.prefix}…</span> · создан{' '}
                    {formatDateTime(key.created_at)} ·{' '}
                    {key.last_used_at
                      ? `использован ${formatRelative(key.last_used_at)}`
                      : 'ещё не использован'}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="danger"
                  aria-label={`Отозвать ключ «${key.name}»`}
                  icon={<Trash2 size={16} />}
                  onClick={() => {
                    if (created?.id === key.id) setCreated(null)
                    revoke.mutate(key.id, {
                      onSuccess: () => toast.success(`Ключ «${key.name}» отозван`),
                    })
                  }}
                />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </Card>
  )
}
