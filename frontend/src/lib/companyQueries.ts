import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi } from './company'
import type { Company, MemberChange, PersonInput, TeamBrief, TeamInput } from './company'
import { keys } from './queries'

export const companyKeys = {
  company: ['company'] as const,
  invite: (token: string) => ['invite', token] as const,
}

// The list shows whether people came in: refreshed while the page is open.
const COMPANY_POLL_MS = 30_000

export const useCompany = (isEnabled = true) =>
  useQuery({
    queryKey: companyKeys.company,
    queryFn: companyApi.company,
    enabled: isEnabled,
    refetchInterval: COMPANY_POLL_MS,
  })

/** Everything a change can touch: the space, and the account's place in it. */
function useRefresh() {
  const client = useQueryClient()
  return async (company?: Company) => {
    if (company) client.setQueryData(companyKeys.company, company)
    await Promise.all([
      client.invalidateQueries({ queryKey: companyKeys.company }),
      client.invalidateQueries({ queryKey: keys.me }),
    ])
  }
}

export function useCreateCompany() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ name, about }: { name: string; about: string }) =>
      companyApi.createCompany(name, about),
    onSuccess: refresh,
  })
}

export function useUpdateCompany() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: companyApi.updateCompany,
    onSuccess: refresh,
  })
}

/** The profile a description suggests; nothing is saved. */
export const useDraftTeam = () =>
  useMutation({ mutationFn: (brief: TeamBrief) => companyApi.draftTeam(brief) })

export function useSaveTeam() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, team }: { id: string | null; team: TeamInput }) =>
      id ? companyApi.updateTeam(id, team) : companyApi.createTeam(team),
    onSuccess: () => refresh(),
  })
}

export function useDeleteTeam() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: companyApi.deleteTeam, onSuccess: () => refresh() })
}

export function useAddMembers() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ teamId, people }: { teamId: string; people: PersonInput[] }) =>
      companyApi.addMembers(teamId, people),
    onSuccess: () => refresh(),
  })
}

export function useUpdateMember() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: ({ id, change }: { id: string; change: MemberChange }) =>
      companyApi.updateMember(id, change),
    onSuccess: () => refresh(),
  })
}

export function useRenewInvite() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: companyApi.renewInvite, onSuccess: () => refresh() })
}

export function useRemoveMember() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: companyApi.removeMember, onSuccess: () => refresh() })
}

/** Who an invitation is for; a used or old link answers 404 and is not retried. */
export const useInvite = (token: string) =>
  useQuery({
    queryKey: companyKeys.invite(token),
    queryFn: () => companyApi.invite(token),
    retry: false,
    staleTime: Infinity,
  })
