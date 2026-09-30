import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from './api'
import type {
  Digest,
  DigestSummary,
  Profile,
  ProfileSpec,
  ProgressEvent,
  Source,
  SourceCreate,
} from './api'

export const keys = {
  meta: ['meta'] as const,
  profiles: ['profiles'] as const,
  sources: ['sources'] as const,
  digests: ['digests'] as const,
  digest: (id: string) => ['digest', id] as const,
}

const ARTICLES_PAGE = 30
const ACTIVE_POLL_MS = 4_000

const isBuilding = (digest: { status: string } | undefined) =>
  digest?.status === 'queued' || digest?.status === 'running'

export const useMeta = () =>
  useQuery({ queryKey: keys.meta, queryFn: api.meta, refetchInterval: 60_000 })

export const useProfiles = () => useQuery({ queryKey: keys.profiles, queryFn: api.profiles })

export const useSources = () =>
  useQuery({ queryKey: keys.sources, queryFn: api.sources, refetchInterval: 30_000 })

/** The list is polled only while some digest in it is still being built. */
export const useDigests = () =>
  useQuery({
    queryKey: keys.digests,
    queryFn: () => api.digests(),
    refetchInterval: (query) => (query.state.data?.some(isBuilding) ? ACTIVE_POLL_MS : false),
  })

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

export function useSaveProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, spec }: { id: string | null; spec: ProfileSpec }) =>
      id ? api.updateProfile(id, spec) : api.createProfile(spec),
    onSuccess: (profile) => {
      // Put the saved version into the cache at once: the editor compares its
      // draft with it, and must not look "unsaved" until a refetch arrives.
      client.setQueryData<Profile[]>(keys.profiles, (list = []) =>
        list.some((item) => item.id === profile.id)
          ? list.map((item) => (item.id === profile.id ? profile : item))
          : [...list, profile],
      )
      return client.invalidateQueries({ queryKey: keys.profiles })
    },
  })
}

export function useDeleteProfile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.profiles }),
  })
}

export function useCreateDigest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ profileId, days }: { profileId: string; days: number }) =>
      api.createDigest(profileId, days),
    onSuccess: (created) => {
      client.setQueryData<DigestSummary[]>(keys.digests, (list) => [created, ...(list ?? [])])
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
