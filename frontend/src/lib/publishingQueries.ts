import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { publishingApi } from './publishing'
import type { ChannelSettings, Post, PostContent } from './publishing'

export const publishingKeys = {
  defaults: ['publishing', 'defaults'] as const,
  bots: ['publishing', 'bots'] as const,
  channels: ['publishing', 'channels'] as const,
  posts: (channelId?: string) => ['publishing', 'posts', channelId ?? 'all'] as const,
}

type Area = 'bots' | 'channels' | 'posts'

// Posts change state on their own (written, sent): followed while any is moving.
const MOVING: Post['status'][] = ['composing', 'queued', 'sending']
const POLL_MS = 3_000
const IDLE_POLL_MS = 20_000

export const usePublishingDefaults = () =>
  useQuery({
    queryKey: publishingKeys.defaults,
    queryFn: publishingApi.defaults,
    staleTime: Infinity,
  })

export const useBots = () =>
  useQuery({ queryKey: publishingKeys.bots, queryFn: publishingApi.bots })

export const useChannels = () =>
  useQuery({
    queryKey: publishingKeys.channels,
    queryFn: publishingApi.channels,
    refetchInterval: 30_000,
  })

export const usePosts = (channelId?: string) =>
  useQuery({
    queryKey: publishingKeys.posts(channelId),
    queryFn: () => publishingApi.posts(channelId),
    // Another channel's posts must not stand in for this one's while it loads.
    placeholderData: undefined,
    refetchInterval: (state) =>
      state.state.data?.some((post) => MOVING.includes(post.status)) ? POLL_MS : IDLE_POLL_MS,
  })

/** Refetch what a change touched, and only that. */
function useRefresh(...areas: Area[]) {
  const client = useQueryClient()
  return () =>
    Promise.all(areas.map((area) => client.invalidateQueries({ queryKey: ['publishing', area] })))
}

// Changes made from a card or a row show nothing on their own when they fail:
// the toggle or the row just snaps back. They say why in a toast. Adding a bot
// or a channel shows its error in the form instead.
const sayWhy = (error: Error) => toast.error(error.message)

export function useAddBot() {
  const refresh = useRefresh('bots')
  return useMutation({ mutationFn: publishingApi.addBot, onSuccess: refresh })
}

export function useDeleteBot() {
  // A bot takes its channels and their posts with it.
  const refresh = useRefresh('bots', 'channels', 'posts')
  return useMutation({ mutationFn: publishingApi.deleteBot, onSuccess: refresh, onError: sayWhy })
}

export function useAddChannel() {
  const refresh = useRefresh('bots', 'channels')
  return useMutation({
    mutationFn: (vars: { botId: string; chat: string; profileId: string | null }) =>
      publishingApi.addChannel(vars.botId, vars.chat, vars.profileId),
    onSuccess: refresh,
  })
}

export function useUpdateChannel() {
  const refresh = useRefresh('channels')
  return useMutation({
    mutationFn: (vars: {
      id: string
      enabled?: boolean
      profile_id?: string | null
      bot_id?: string
      settings?: ChannelSettings
    }) => {
      const { id, ...patch } = vars
      return publishingApi.updateChannel(id, patch)
    },
    onSuccess: refresh,
    onError: sayWhy,
  })
}

export function useDeleteChannel() {
  const refresh = useRefresh('bots', 'channels', 'posts')
  return useMutation({
    mutationFn: publishingApi.deleteChannel,
    onSuccess: refresh,
    onError: sayWhy,
  })
}

// A post's change also moves the counters on its channel's card.
export function useCreatePost() {
  const refresh = useRefresh('posts', 'channels')
  return useMutation({
    mutationFn: (vars: { channelId: string; kind?: 'news' | 'digest'; publish?: boolean }) =>
      publishingApi.createPost(vars.channelId, { kind: vars.kind, publish: vars.publish }),
    onSuccess: refresh,
    onError: sayWhy,
  })
}

export function useUpdatePost() {
  const refresh = useRefresh('posts', 'channels')
  return useMutation({
    mutationFn: (vars: { id: string; content?: PostContent; approve?: boolean }) =>
      publishingApi.updatePost(vars.id, { content: vars.content, approve: vars.approve }),
    onSuccess: refresh,
    onError: sayWhy,
  })
}

export function usePublishPost() {
  const refresh = useRefresh('posts', 'channels')
  return useMutation({ mutationFn: publishingApi.publishPost, onSuccess: refresh, onError: sayWhy })
}

export function useDeletePost() {
  const refresh = useRefresh('posts', 'channels')
  return useMutation({ mutationFn: publishingApi.deletePost, onSuccess: refresh, onError: sayWhy })
}
