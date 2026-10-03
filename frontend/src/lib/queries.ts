import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError, api } from './api'
import type {
  Digest,
  DigestSummary,
  FeedItem,
  FeedPage,
  Me,
  Adaptation,
  DigestSchedule,
  ScheduleInput,
  Placement,
  Profile,
  ProfileSpec,
  ProgressEvent,
  ReactionKind,
  SharedProfile,
  Resume,
  Settings,
  FeedOrder,
  Source,
  SourceCreate,
  Video,
  DigestPeriod,
} from './api'

export const keys = {
  meta: ['meta'] as const,
  schedules: ['digest-schedules'] as const,
  mcpKeys: ['mcp-keys'] as const,
  me: ['me'] as const,
  resume: ['resume'] as const,
  feed: ['feed'] as const,
  saved: ['saved'] as const,
  taste: ['taste'] as const,
  profiles: ['profiles'] as const,
  sources: ['sources'] as const,
  sourceAvatars: ['source-avatars'] as const,
  digests: ['digests'] as const,
  digest: (id: string) => ['digest', id] as const,
  article: (id: number) => ['article', id] as const,
  short: (digestId: string) => ['short', digestId] as const,
}

const ARTICLES_PAGE = 30
const FEED_PAGE = 20
const ACTIVE_POLL_MS = 4_000
const RESUME_POLL_MS = 1_200
const SHORT_POLL_MS = 2_500
const SCHEDULE_POLL_MS = 60_000
const FRESH_POLL_MS = 120_000

const isBuilding = (digest: { status: string } | undefined) =>
  digest?.status === 'queued' || digest?.status === 'running'

/** The administrator's analytics; refreshed every minute while open. */
export const useAnalytics = (days: number, guests: boolean, isEnabled: boolean) =>
  useQuery({
    queryKey: ['analytics', days, guests],
    queryFn: () => api.analytics(days, guests),
    enabled: isEnabled,
    refetchInterval: 60_000,
  })

export const useMeta = () =>
  useQuery({ queryKey: keys.meta, queryFn: api.meta, refetchInterval: 60_000 })

export const useProfiles = () => useQuery({ queryKey: keys.profiles, queryFn: api.profiles })

export const useSources = () =>
  useQuery({ queryKey: keys.sources, queryFn: api.sources, refetchInterval: 30_000 })

/** The polls of the last day: asked again with each poll of the catalogue. */
export const useSourceHealth = () =>
  useQuery({ queryKey: ['source-health'], queryFn: api.sourceHealth, refetchInterval: 5 * 60_000 })

/** Which sources have a picture; asked once a session, pictures change rarely. */
export const useSourceAvatars = () =>
  useQuery({ queryKey: keys.sourceAvatars, queryFn: api.sourceAvatars, staleTime: 30 * 60_000 })

/** The list is polled only while some digest in it is still being built. */
export function useDigests() {
  const client = useQueryClient()
  return useQuery({
    queryKey: keys.digests,
    queryFn: () => api.digests(),
    // Fast while something builds; once a minute while a schedule may add a
    // digest by itself, so it shows up without a reload.
    refetchInterval: (query) =>
      query.state.data?.some(isBuilding)
        ? ACTIVE_POLL_MS
        : client.getQueryData<DigestSchedule[]>(keys.schedules)?.length
          ? SCHEDULE_POLL_MS
          : false,
  })
}

/**
 * One digest. While it is being built the row is polled as well as streamed:
 * if the event stream breaks, the page still reaches the finished state.
 */
export const useDigest = (id: string | undefined) =>
  useQuery({
    queryKey: keys.digest(id ?? ''),
    queryFn: () => api.digest(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) => (isBuilding(query.state.data) ? ACTIVE_POLL_MS : false),
  })

/** Put a profile the server returned into the cached list, new or replaced. */
function putProfile(client: QueryClient, profile: Profile): void {
  client.setQueryData<Profile[]>(keys.profiles, (list = []) =>
    list.some((item) => item.id === profile.id)
      ? list.map((item) => (item.id === profile.id ? profile : item))
      : [...list, profile],
  )
}

export function useSaveProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, spec }: { id: string | null; spec: ProfileSpec }) =>
      id ? api.updateProfile(id, spec) : api.createProfile(spec),
    onSuccess: (profile) => {
      // Put the saved version into the cache at once: the editor compares its
      // draft with it, and must not look "unsaved" until a refetch arrives.
      putProfile(client, profile)
      // Interests are part of the reader's taste.
      void client.invalidateQueries({ queryKey: keys.feed })
      void client.invalidateQueries({ queryKey: keys.taste })
      return client.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

export function useDeleteProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.feed })
      void client.invalidateQueries({ queryKey: keys.taste })
      return client.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

export function useCreateDigest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ profileId, period }: { profileId: string; period: DigestPeriod }) =>
      api.createDigest(profileId, period),
    onSuccess: (created) => {
      client.setQueryData<DigestSummary[]>(keys.digests, (list) => [created, ...(list ?? [])])
    },
  })
}

export function useCreateDigestsForBoth() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ profileId, period }: { profileId: string; period: DigestPeriod }) =>
      api.createDigestsForBoth(profileId, period),
    onSuccess: (created) => {
      client.setQueryData<DigestSummary[]>(keys.digests, (list) => [...created, ...(list ?? [])])
    },
  })
}

export function useDeleteDigest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.deleteDigest,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.digests }),
  })
}

/** The digest's short video, polled while it is being made. The server gives
 * up on a stuck video by itself, so the polling always ends. */
export const useShort = (digestId: string, isEnabled: boolean) =>
  useQuery({
    queryKey: keys.short(digestId),
    queryFn: () => api.short(digestId),
    enabled: isEnabled,
    refetchInterval: (query) =>
      query.state.status !== 'error' && isBuilding(query.state.data ?? undefined)
        ? SHORT_POLL_MS
        : false,
  })

export function useCreateShort(digestId: string) {
  const client = useQueryClient()
  const key = keys.short(digestId)
  return useMutation({
    mutationFn: (voice: string | null) => api.createShort(digestId, voice),
    // A poll that started before the order would bring back the old video
    // and stop the polling of the new one.
    onMutate: () => client.cancelQueries({ queryKey: key }),
    onSuccess: (video) => client.setQueryData<Video | null>(key, video),
    // Refused (another video is being made, say): show what the server has.
    onSettled: () => client.invalidateQueries({ queryKey: key }),
  })
}

export function useSourceMutations() {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: keys.sources })
  return {
    create: useMutation({
      mutationFn: (source: SourceCreate) => api.createSource(source),
      onSuccess: refresh,
    }),
    toggle: useMutation({
      mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
        api.updateSource(id, { enabled }),
      // Flip the switch at once; the server answer confirms or reverts it.
      onMutate: async ({ id, enabled }) => {
        await client.cancelQueries({ queryKey: keys.sources })
        const previous = client.getQueryData<Source[]>(keys.sources)
        client.setQueryData<Source[]>(keys.sources, (list) =>
          list?.map((source) => (source.id === id ? { ...source, enabled } : source)),
        )
        return { previous }
      },
      onError: (_error, _variables, context) =>
        client.setQueryData(keys.sources, context?.previous),
      onSettled: refresh,
    }),
    remove: useMutation({ mutationFn: api.deleteSource, onSuccess: refresh }),
    refreshOne: useMutation({ mutationFn: api.refreshSource }),
    refreshAll: useMutation({ mutationFn: api.refreshSources }),
  }
}

/** How often the worker's answer about an address is asked for while it looks. */
const DETECT_POLL_MS = 1_500

/**
 * What an address is and how to read it. The ingest worker finds out, a
 * protected site in the browser, so the answer is asked for until it comes.
 */
export function useSourceDetection() {
  const start = useMutation({
    mutationFn: ({ address, linkSelector }: { address: string; linkSelector?: string }) =>
      api.detectSource(address, linkSelector),
  })
  const requestId = start.data?.request_id
  const result = useQuery({
    queryKey: ['source-detect', requestId],
    queryFn: () => api.detectResult(requestId as string),
    enabled: Boolean(requestId),
    refetchInterval: (query) => (query.state.data?.status === 'done' ? false : DETECT_POLL_MS),
  })
  return { start, result }
}

/** An article as the reader shows it; the page behind it is read once, by the API. */
export const useArticle = (id: number, isEnabled: boolean) =>
  useQuery({
    queryKey: keys.article(id),
    queryFn: () => api.article(id),
    enabled: isEnabled,
    // A text read from its page does not change. One the site would not give
    // is asked for again: the API reads the page again after a while.
    staleTime: (query) => (query.state.data?.complete ? Infinity : 60_000),
    // Another article is never shown in place of this one.
    placeholderData: undefined,
  })

export function useArticles(params: { q: string; category: string[] }) {
  return useInfiniteQuery({
    queryKey: ['articles', params],
    queryFn: ({ pageParam }) =>
      api.articles({ ...params, language: [], limit: ARTICLES_PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length
      return next < last.total ? next : undefined
    },
    placeholderData: keepPreviousData,
  })
}

export const useTimeline = (days: number) =>
  useQuery({ queryKey: ['timeline', days], queryFn: () => api.timeline(days), staleTime: 60_000 })

export const useComparison = (base: string | undefined, other: string | undefined) =>
  useQuery({
    queryKey: ['compare', base, other],
    queryFn: () => api.compare(base as string, other as string),
    enabled: Boolean(base && other && base !== other),
  })

/** The part of a profile that decides what gets selected. */
function selectionKey(spec: ProfileSpec) {
  const { interests, exclusions, min_score, max_items, languages, categories } = spec
  return { interests, exclusions, min_score, max_items, languages, categories }
}

function canPreview(spec: ProfileSpec | null): spec is ProfileSpec {
  return (
    spec !== null &&
    spec.interests.length > 0 &&
    spec.interests.every((interest) => interest.title.trim().length >= 2)
  )
}

/**
 * Preview for a profile draft, debounced so typing does not flood the API.
 * The name and the role do not influence selection, so editing them neither
 * refetches nor adds a cache entry.
 */
export function usePreview(spec: ProfileSpec | null, days: number, delayMs = 450) {
  const [settled, setSettled] = useState(spec)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(spec), delayMs)
    return () => clearTimeout(timer)
  }, [spec, delayMs])

  const valid = canPreview(settled)
  const query = useQuery({
    queryKey: ['preview', valid ? selectionKey(settled) : null, days],
    queryFn: ({ signal }) =>
      api.preview({ ...(settled as ProfileSpec), name: 'preview', role: '' }, days, signal),
    enabled: valid,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    retry: false,
  })
  // An invalid draft has no preview; do not keep showing the previous one.
  return { ...query, data: valid ? query.data : undefined, isValid: valid }
}

/**
 * Follow a digest build over Server-Sent Events. The latest event is returned
 * for the progress bar; when the build ends, the cached digest and the list
 * are refreshed so the finished issue appears without a manual reload.
 */
export function useDigestProgress(
  digest: DigestSummary | Digest | undefined,
): ProgressEvent | null {
  const client = useQueryClient()
  const [latest, setLatest] = useState<{ id: string; event: ProgressEvent } | null>(null)
  const id = digest?.id
  const active = isBuilding(digest)

  useEffect(() => {
    if (!id || !active) return
    const source = new EventSource(api.eventsUrl(id))
    const refetch = () => {
      void client.invalidateQueries({ queryKey: keys.digest(id) })
      void client.invalidateQueries({ queryKey: keys.digests })
    }
    source.addEventListener('progress', (message) => {
      let data: ProgressEvent
      try {
        data = JSON.parse((message as MessageEvent<string>).data) as ProgressEvent
      } catch {
        return
      }
      setLatest({ id, event: data })
      if (data.status === 'done' || data.status === 'failed') {
        source.close()
        refetch()
      }
    })
    // Any error (the server closing the stream, a gateway hiccup, a 404):
    // ask the API where the build stands. EventSource reconnects on its own
    // unless it gave up, and the polling in useDigest covers that case.
    source.onerror = refetch
    return () => source.close()
  }, [id, active, client])

  // An event belongs to the digest it was received for; after switching to
  // another issue the old one must not leak into its progress bar.
  return active && latest !== null && latest.id === id ? latest.event : null
}

/** Drop everything cached for a reader; who is signed in is handled separately. */
function forgetReaderData(client: QueryClient): void {
  client.removeQueries({
    predicate: (query) => query.queryKey[0] !== 'me' && query.queryKey[0] !== 'meta',
  })
}

/** Set by signing out on purpose: no guest is made behind the reader's back then. */
const SIGNED_OUT_KEY = 'radar-signed-out'

function rememberSignedOut(isSignedOut: boolean): void {
  try {
    if (isSignedOut) sessionStorage.setItem(SIGNED_OUT_KEY, '1')
    else sessionStorage.removeItem(SIGNED_OUT_KEY)
  } catch {
    // Storage may be blocked; the worst case is one guest too many.
  }
}

function hasSignedOut(): boolean {
  try {
    return sessionStorage.getItem(SIGNED_OUT_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * Where the server needs no sign-in, a visitor with no session becomes a guest
 * of their own straight away: the jury asked for no sign-in screen. A failure
 * here leaves the sign-in page, which has the same button.
 */
async function enterAsGuest(client: QueryClient): Promise<Me | null> {
  if (hasSignedOut()) return null
  try {
    const meta = await client.fetchQuery({ queryKey: keys.meta, queryFn: api.meta })
    if (meta.sign_in_required) return null
    await api.demoLogin()
    return await api.me()
  } catch {
    return null
  }
}

/**
 * Who is signed in; `null` means nobody, and the app shows the sign-in page.
 * Checked again when the tab regains focus: if another tab signed in as
 * someone else, the data cached for the previous reader is dropped.
 */
export function useMe() {
  const client = useQueryClient()
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      const previous = client.getQueryData<Me | null>(keys.me)
      const current = (await api.me()) ?? (await enterAsGuest(client))
      if (previous && previous.id !== current?.id) forgetReaderData(client)
      return current
    },
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  })
}

/**
 * Sign in, register or enter as a guest. Everything cached belongs to the
 * previous reader (or to nobody), so it is dropped before the new one is
 * looked up. If the session did not take (the browser refused the cookie),
 * the sign-in fails loudly instead of leaving the form silently as it was.
 */
export function useSignIn() {
  const client = useQueryClient()
  const enter = async () => {
    rememberSignedOut(false)
    forgetReaderData(client)
    const me = await client.fetchQuery({ queryKey: keys.me, queryFn: api.me, staleTime: 0 })
    if (!me) {
      throw new ApiError(401, 'Вход не сохранился: браузер не принял cookie сессии.')
    }
  }
  return {
    login: useMutation({
      mutationFn: async ({ email, password }: { email: string; password: string }) => {
        await api.login(email, password)
        await enter()
      },
    }),
    register: useMutation({
      mutationFn: async (form: { email: string; password: string; displayName: string }) => {
        await api.register(form.email, form.password, form.displayName)
        await enter()
      },
    }),
    demo: useMutation({
      mutationFn: async () => {
        await api.demoLogin()
        await enter()
      },
    }),
  }
}

export function useSignOut() {
  const client = useQueryClient()
  const leave = () => {
    rememberSignedOut(true)
    // Telling the route guard first: it unmounts the pages, and only then
    // their data is removed.
    client.setQueryData(keys.me, null)
    forgetReaderData(client)
  }
  return {
    logout: useMutation({ mutationFn: api.logout, onSuccess: leave }),
    deleteAccount: useMutation({ mutationFn: api.deleteAccount, onSuccess: leave }),
  }
}

/** The resume changed what the reader is: everything derived from it is stale. */
function refreshReader(client: QueryClient): void {
  void client.invalidateQueries({ queryKey: keys.me })
  void client.invalidateQueries({ queryKey: keys.taste })
  void client.invalidateQueries({ queryKey: keys.feed })
}

/** Give up polling after this long: the worker has its own, longer, timeout. */
const RESUME_POLL_LIMIT_MS = 5 * 60_000

export const isResumeStuck = (resume: Resume | null | undefined, now = Date.now()) =>
  resume?.status === 'processing' &&
  now - new Date(resume.created_at).getTime() > RESUME_POLL_LIMIT_MS

/**
 * The resume, polled while the worker is still reading it; `null` means none.
 * When the analysis finishes, the feed and the taste are refreshed: they were
 * built without it.
 */
export function useResume(isEnabled = true) {
  const client = useQueryClient()
  return useQuery({
    queryKey: keys.resume,
    queryFn: async () => {
      const previous = client.getQueryData<Resume | null>(keys.resume)
      const current = await api.resume()
      if (previous?.status === 'processing' && current?.status !== 'processing') {
        refreshReader(client)
      }
      return current
    },
    enabled: isEnabled,
    refetchInterval: (query) =>
      query.state.data?.status === 'processing' && !isResumeStuck(query.state.data)
        ? RESUME_POLL_MS
        : false,
  })
}

export function useResumeMutations() {
  const client = useQueryClient()
  return {
    upload: useMutation({
      mutationFn: (file: File) => api.uploadResume(file),
      onSuccess: (resume) => {
        client.setQueryData(keys.resume, resume)
        void client.invalidateQueries({ queryKey: keys.me })
      },
    }),
    remove: useMutation({
      mutationFn: api.deleteResume,
      onSuccess: () => {
        client.setQueryData(keys.resume, null)
        refreshReader(client)
      },
    }),
  }
}

type FeedCursor = { offset: number; snapshot?: string }

const nextCursor = (last: FeedPage): FeedCursor | undefined => {
  const next = last.offset + last.items.length
  return next < last.total && last.items.length > 0
    ? { offset: next, snapshot: last.snapshot ?? undefined }
    : undefined
}

/**
 * The personal feed. Every page after the first asks for the snapshot the
 * first one was cut from, so reactions between pages do not reshuffle it.
 * Rebuilding (a refetch) starts a new snapshot.
 */
export const useFeed = (order: FeedOrder) =>
  useInfiniteQuery({
    queryKey: [...keys.feed, order],
    queryFn: ({ pageParam }) => api.feed(order, FEED_PAGE, pageParam.offset, pageParam.snapshot),
    initialPageParam: { offset: 0 } as FeedCursor,
    getNextPageParam: nextCursor,
    // The order changes only when the reader asks for it: a feed that
    // reshuffles under the cursor after every like is unreadable.
    staleTime: Infinity,
  })

/**
 * Asks now and then whether the feed on screen has fallen behind: sources are
 * read every quarter of an hour, and a new relevant article is then offered.
 */
export const useFeedFresh = (since: string | null | undefined) =>
  useQuery({
    queryKey: ['feed-fresh', since],
    queryFn: () => api.feedFresh(since ?? ''),
    enabled: Boolean(since),
    refetchInterval: FRESH_POLL_MS,
    // A hidden tab does not ask; coming back to it does, at once.
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    placeholderData: undefined,
  })

export const useSaved = (isEnabled: boolean) =>
  useInfiniteQuery({
    queryKey: keys.saved,
    queryFn: ({ pageParam }) => api.saved(FEED_PAGE, pageParam.offset),
    initialPageParam: { offset: 0 } as FeedCursor,
    getNextPageParam: nextCursor,
    enabled: isEnabled,
  })

export const useTaste = () => useQuery({ queryKey: keys.taste, queryFn: api.taste })

/** Reactions to a fixed set of articles, e.g. the items of an open digest. */
export const useReactions = (articleIds: number[]) =>
  useQuery({
    queryKey: ['reactions', articleIds],
    queryFn: () => api.reactions(articleIds),
    enabled: articleIds.length > 0,
    staleTime: 30_000,
  })

type Feedback = {
  articleId: number
  kind: ReactionKind
  isActive: boolean
  context: 'feed' | 'digest'
  placement?: Placement
}

type FeedPages = { pages: FeedPage[]; pageParams: unknown[] }

/** What the reaction list looks like after one signal is set or cleared. */
export function applyReaction(
  current: ReactionKind[],
  kind: ReactionKind,
  isActive: boolean,
): ReactionKind[] {
  const opposite = kind === 'like' ? 'dislike' : kind === 'dislike' ? 'like' : null
  const rest = current.filter((item) => item !== kind && item !== opposite)
  return isActive ? [...rest, kind] : rest
}

/** Set the reactions of one article wherever it is cached. */
function writeReactions(
  client: QueryClient,
  articleId: number,
  change: (current: ReactionKind[]) => ReactionKind[],
): void {
  const setItem = (item: FeedItem): FeedItem =>
    item.article_id === articleId ? { ...item, reactions: change(item.reactions) } : item
  // The feed is cached once per order: every copy of the article changes.
  for (const queryKey of [keys.feed, keys.saved]) {
    client.setQueriesData<FeedPages>({ queryKey }, (data) =>
      data
        ? {
            ...data,
            pages: data.pages.map((page) => ({ ...page, items: page.items.map(setItem) })),
          }
        : data,
    )
  }
  client.setQueriesData<Record<string, ReactionKind[]>>(
    { queryKey: ['reactions'] },
    (data) => data && { ...data, [articleId]: change(data[articleId] ?? []) },
  )
}

/** The reactions of one article as the screen shows them now. */
function readReactions(client: QueryClient, articleId: number): ReactionKind[] {
  for (const queryKey of [keys.feed, keys.saved]) {
    for (const [, data] of client.getQueriesData<FeedPages>({ queryKey })) {
      const item = data?.pages
        .flatMap((page) => page.items)
        .find((it) => it.article_id === articleId)
      if (item) return item.reactions
    }
  }
  for (const [, data] of client.getQueriesData<Record<string, ReactionKind[]>>({
    queryKey: ['reactions'],
  })) {
    if (data?.[articleId]) return data[articleId]
  }
  return []
}

/**
 * Send a reader signal. The button reflects it at once; if the request fails,
 * only that article goes back to what it was, so other reactions made in the
 * meantime stay. Signals are sent one after another: a like and an unlike
 * clicked in quick succession reach the server in that order.
 */
export function useFeedback() {
  const client = useQueryClient()
  return useMutation({
    scope: { id: 'feedback' },
    mutationFn: ({ articleId, kind, isActive, context, placement }: Feedback) =>
      api.feedback(articleId, kind, isActive, context, placement),
    onMutate: async ({ articleId, kind, isActive }) => {
      // A reactions request in flight would overwrite the optimistic state
      // with an older answer. The feed itself is not cancelled: that would
      // abort a "show more" or a rebuild the reader asked for.
      await client.cancelQueries({ queryKey: ['reactions'] })
      const previous = readReactions(client, articleId)
      writeReactions(client, articleId, (current) => applyReaction(current, kind, isActive))
      return { previous }
    },
    onError: (_error, { articleId }, context) => {
      if (context) writeReactions(client, articleId, () => context.previous)
    },
    onSuccess: (_data, feedback) => {
      void client.invalidateQueries({ queryKey: keys.taste })
      if (feedback.kind === 'save') void client.invalidateQueries({ queryKey: keys.saved })
    },
  })
}

export const useMcpKeys = () => useQuery({ queryKey: keys.mcpKeys, queryFn: api.mcpKeys })

export function useCreateMcpKey() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.createMcpKey,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.mcpKeys }),
  })
}

export function useRevokeMcpKey() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.revokeMcpKey,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.mcpKeys }),
  })
}

const LOOK = ['profile-look'] as const

/** A profile's icon and colour: shown at once, confirmed or reverted by the server. */
export function useSetProfileLook() {
  const client = useQueryClient()
  return useMutation({
    mutationKey: LOOK,
    // One after another: quick picks reach the server, behind any replica, in
    // the order they were made.
    scope: { id: 'profile-look' },
    mutationFn: ({ id, icon, color }: { id: string; icon: string | null; color: string | null }) =>
      api.setProfileLook(id, { icon, color }),
    onMutate: async ({ id, icon, color }) => {
      await client.cancelQueries({ queryKey: keys.profiles })
      const previous = client.getQueryData<Profile[]>(keys.profiles)
      client.setQueryData<Profile[]>(keys.profiles, (list) =>
        list?.map((profile) => (profile.id === id ? { ...profile, icon, color } : profile)),
      )
      return { previous }
    },
    onError: (_error, _vars, context) => client.setQueryData(keys.profiles, context?.previous),
    // Only the last pick refetches: an earlier answer would overwrite the
    // later picks still shown ahead of the server.
    onSettled: () =>
      client.isMutating({ mutationKey: LOOK }) === 1
        ? client.invalidateQueries({ queryKey: keys.profiles })
        : undefined,
  })
}

/** The owner opens or closes the link of a profile. */
export function useProfileLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, isShared }: { id: string; isShared: boolean }) =>
      isShared ? api.shareProfile(id) : api.unshareProfile(id),
    onSuccess: (profile) => putProfile(client, profile),
  })
}

const sharedKey = (token: string) => ['shared-profile', token] as const

/** What a link hands over. Never the answer for another link meanwhile. */
export const useSharedProfile = (token: string) =>
  useQuery({
    queryKey: sharedKey(token),
    queryFn: () => api.sharedProfile(token),
    placeholderData: undefined,
    staleTime: 0,
  })

/** Add a copy of a shared profile; the list and the reader's taste follow. */
export function useAcceptSharedProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.acceptSharedProfile,
    onSuccess: (profile, token) => {
      putProfile(client, profile)
      // The link opened again says the profile is already there.
      client.setQueryData<SharedProfile>(sharedKey(token), (shared) =>
        shared ? { ...shared, own_id: profile.id } : shared,
      )
      void client.invalidateQueries({ queryKey: keys.feed })
      void client.invalidateQueries({ queryKey: keys.taste })
      void client.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

const adaptationKey = (profileId: string) => ['adaptation', profileId] as const

/** What a profile learned from the reader. Refreshed now and then: it is recomputed in the background. */
export const useAdaptation = (profileId: string | null) =>
  useQuery({
    queryKey: adaptationKey(profileId ?? ''),
    queryFn: () => api.adaptation(profileId as string),
    enabled: Boolean(profileId),
    refetchInterval: 60_000,
  })

function putAdaptation(client: QueryClient, profileId: string, adaptation: Adaptation): void {
  client.setQueryData(adaptationKey(profileId), adaptation)
  // The feed and the profile list carry the adaptive flag and its effects.
  void client.invalidateQueries({ queryKey: keys.profiles })
  void client.invalidateQueries({ queryKey: keys.feed })
  void client.invalidateQueries({ queryKey: keys.taste })
}

export function useSetAdaptive() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ profileId, adaptive }: { profileId: string; adaptive: boolean }) =>
      api.setAdaptive(profileId, adaptive),
    onSuccess: (adaptation, { profileId }) => putAdaptation(client, profileId, adaptation),
  })
}

export function useResetAdaptation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.resetAdaptation,
    onSuccess: (adaptation, profileId) => putAdaptation(client, profileId, adaptation),
  })
}

/** Take or turn down a suggestion; either way it leaves the list at once. */
export function useDecideSuggestion() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({
      profileId,
      suggestionId,
      isAccepted,
    }: {
      profileId: string
      suggestionId: string
      isAccepted: boolean
    }) =>
      isAccepted
        ? api.acceptSuggestion(profileId, suggestionId)
        : api.dismissSuggestion(profileId, suggestionId).then(() => null),
    onSuccess: (profile, { profileId, suggestionId }) => {
      client.setQueryData<Adaptation>(adaptationKey(profileId), (current) =>
        current
          ? {
              ...current,
              suggestions: current.suggestions.filter((item) => item.id !== suggestionId),
            }
          : current,
      )
      if (profile) {
        putProfile(client, profile)
        void client.invalidateQueries({ queryKey: keys.feed })
        void client.invalidateQueries({ queryKey: keys.taste })
      }
      // Not awaited: the caller's onSuccess (the editor's draft) must run at once.
      void client.invalidateQueries({ queryKey: adaptationKey(profileId) })
    },
  })
}

/** The reader's settings: shown at once, put back if the server refuses them. */
export function useUpdateSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.updateSettings,
    onMutate: async (settings: Partial<Settings>) => {
      await client.cancelQueries({ queryKey: keys.me })
      const previous = client.getQueryData<Me | null>(keys.me)
      client.setQueryData<Me | null>(keys.me, (me) => (me ? { ...me, ...settings } : me))
      return { previous }
    },
    onError: (_error, _settings, context) => {
      // Only the setting goes back: the picture may have changed meanwhile.
      const before = context?.previous
      if (before) {
        client.setQueryData<Me | null>(keys.me, (me) =>
          me ? { ...me, feed_view: before.feed_view, feed_order: before.feed_order } : me,
        )
      }
    },
    // Two quick clicks may reach the server in either order: it has the last word.
    onSettled: () => client.invalidateQueries({ queryKey: keys.me }),
  })
}

/** The reader's picture: a new address in the cached "me" at once. */
export function useAvatar() {
  const client = useQueryClient()
  const put = (avatarUrl: string | null) =>
    client.setQueryData<Me | null>(keys.me, (me) => (me ? { ...me, avatar_url: avatarUrl } : me))
  return {
    upload: useMutation({
      mutationFn: api.uploadAvatar,
      onSuccess: ({ avatar_url }) => put(avatar_url),
    }),
    remove: useMutation({
      mutationFn: api.deleteAvatar,
      onSuccess: () => put(null),
    }),
  }
}

/** Refreshed once a minute: after a run the next slot moves on. */
export const useSchedules = () =>
  useQuery({
    queryKey: keys.schedules,
    queryFn: api.schedules,
    refetchInterval: (query) => (query.state.data?.length ? SCHEDULE_POLL_MS : false),
    refetchOnWindowFocus: true,
  })

/** Set or drop a profile's schedule; the list follows at once. */
export function useSchedule() {
  const client = useQueryClient()
  return {
    save: useMutation({
      mutationFn: ({ profileId, schedule }: { profileId: string; schedule: ScheduleInput }) =>
        api.putSchedule(profileId, schedule),
      onSuccess: (saved) =>
        client.setQueryData<DigestSchedule[]>(keys.schedules, (list = []) => [
          ...list.filter((item) => item.profile_id !== saved.profile_id),
          saved,
        ]),
    }),
    remove: useMutation({
      mutationFn: api.deleteSchedule,
      onSuccess: (_, profileId) =>
        client.setQueryData<DigestSchedule[]>(keys.schedules, (list = []) =>
          list.filter((item) => item.profile_id !== profileId),
        ),
    }),
  }
}
