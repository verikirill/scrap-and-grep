// A company space: teams, their profiles and the accounts of their people.
// Shapes mirror backend/src/radar/api/company_schemas.py.
import { json, request } from './api'
import type { Audience, AvatarPreset, ProfileSpec, User } from './api'

/** "invited": the link works; "expired": a new one is needed; "active": the person came in. */
export type MemberStatus = 'invited' | 'expired' | 'active'

export interface Member {
  id: string
  display_name: string
  email: string
  job_title: string | null
  avatar_preset: AvatarPreset
  team_id: string | null
  /** What their copy of the team profile reads: the cards or the brief. */
  audience: Audience
  status: MemberStatus
  /** Where the person sets a password, while the link works: /invite/<token>. */
  invite_path: string | null
  invite_expires_at: string | null
  last_login_at: string | null
  created_at: string
}

export interface Team {
  id: string
  name: string
  services: string
  spec: ProfileSpec
  icon: string | null
  color: string | null
  members: Member[]
  created_at: string
  updated_at: string
}

export interface Company {
  id: string
  name: string
  about: string
  teams: Team[]
  created_at: string
}

/** What the manager writes about a team; the model reads it. */
export interface TeamBrief {
  name: string
  services: string
  systems: string[]
}

export interface TeamDraft {
  spec: ProfileSpec
  icon: string
  /** The model's name, or "taxonomy" when the table of areas made the draft. */
  drafted_by: string
}

export interface TeamInput extends TeamBrief {
  spec: ProfileSpec
  icon?: string | null
  color?: string | null
}

export interface PersonInput {
  name: string
  email: string
  job_title: string
}

export interface MembersAdded {
  created: Member[]
  skipped: { email: string; reason: string }[]
}

export interface MemberChange {
  team_id?: string
  display_name?: string
  job_title?: string
}

/** Where an account stands in a company space. */
export interface Membership {
  company: string
  team: string | null
  role: 'owner' | 'member'
  job_title: string | null
  /** Who manages the space, as a member sees it. */
  manager: string | null
}

/** What an invited person sees before setting a password. */
export interface Invite {
  display_name: string
  email: string
  company: string
  team: string
  job_title: string | null
  manager: string | null
  audience: Audience
  interests: string[]
}

export const companyApi = {
  /** `null` while the account manages no space. */
  company: () => request<Company | null>('/company'),
  createCompany: (name: string, about: string) =>
    request<Company>('/company', json('POST', { name, about })),
  updateCompany: (change: { name?: string; about?: string }) =>
    request<Company>('/company', json('PATCH', change)),
  draftTeam: (brief: TeamBrief) => request<TeamDraft>('/company/teams/draft', json('POST', brief)),
  createTeam: (team: TeamInput) => request<Team>('/company/teams', json('POST', team)),
  updateTeam: (id: string, team: TeamInput) =>
    request<Team>(`/company/teams/${id}`, json('PUT', team)),
  deleteTeam: (id: string) => request<void>(`/company/teams/${id}`, { method: 'DELETE' }),
  addMembers: (teamId: string, people: PersonInput[]) =>
    request<MembersAdded>(`/company/teams/${teamId}/members`, json('POST', { people })),
  updateMember: (id: string, change: MemberChange) =>
    request<Member>(`/company/members/${id}`, json('PATCH', change)),
  renewInvite: (id: string) => request<Member>(`/company/members/${id}/invite`, { method: 'POST' }),
  removeMember: (id: string) => request<void>(`/company/members/${id}`, { method: 'DELETE' }),
  invite: (token: string) => request<Invite>(`/auth/invite/${encodeURIComponent(token)}`),
  acceptInvite: (token: string, password: string) =>
    request<User>(`/auth/invite/${encodeURIComponent(token)}`, json('POST', { password })),
}

/** The full address of an invitation, to send to the person. */
export function inviteUrl(member: Pick<Member, 'invite_path'>, origin = window.location.origin) {
  return member.invite_path ? `${origin}${member.invite_path}` : null
}
