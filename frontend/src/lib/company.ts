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
  /** A role of the team: its profile instead of the team's. */
  role_id: string | null
  /** How many changes the manager made for this person alone. */
  overrides: number
  /** What their copy of the team profile reads: the cards or the brief. */
  audience: Audience
  status: MemberStatus
  /** Where the person sets a password, while the link works: /invite/<token>. */
  invite_path: string | null
  invite_expires_at: string | null
  last_login_at: string | null
  created_at: string
}

/** A role within a team: two security people may read differently. */
export interface Role {
  id: string
  name: string
  description: string
  spec: ProfileSpec
  created_at: string
  updated_at: string
}

export interface RoleInput {
  name: string
  description: string
  spec?: ProfileSpec
}

export interface Team {
  id: string
  name: string
  services: string
  spec: ProfileSpec
  icon: string | null
  color: string | null
  roles: Role[]
  members: Member[]
  created_at: string
  updated_at: string
}

export interface Company {
  id: string
  name: string
  about: string
  /** Where the logo is served; a new one gets a new address. Null without one. */
  logo_url: string | null
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
  /** null takes the role away. */
  role_id?: string | null
  display_name?: string
  job_title?: string
}

/** One change for many profiles; only what is set changes. */
export interface ProfilePatch {
  add_interests?: { title: string; description?: string; keywords: string[] }[]
  remove_interests?: string[]
  add_exclusions?: string[]
  remove_exclusions?: string[]
  add_systems?: string[]
  audience?: Audience
  max_items?: number
}

/** Who gets the change: the whole team, everyone with one role, or chosen people. */
export type PatchTarget =
  | { scope: 'team' }
  | { scope: 'role'; role_id: string }
  | { scope: 'people'; member_ids: string[] }

/** Where an account stands in a company space. */
export interface Membership {
  company: string
  team: string | null
  role: 'owner' | 'member'
  job_title: string | null
  /** Who manages the space, as a member sees it. */
  manager: string | null
  logo_url?: string | null
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
  logo_url?: string | null
  interests: string[]
}

export const companyApi = {
  /** `null` while the account manages no space. */
  company: () => request<Company | null>('/company'),
  createCompany: (name: string, about: string) =>
    request<Company>('/company', json('POST', { name, about })),
  updateCompany: (change: { name?: string; about?: string }) =>
    request<Company>('/company', json('PATCH', change)),
  /** The picture goes as the raw body; the server redraws it in its own proportions. */
  uploadLogo: (file: File) =>
    request<Company>('/company/logo', {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    }),
  deleteLogo: () => request<Company>('/company/logo', { method: 'DELETE' }),
  draftTeam: (brief: TeamBrief) => request<TeamDraft>('/company/teams/draft', json('POST', brief)),
  createTeam: (team: TeamInput) => request<Team>('/company/teams', json('POST', team)),
  updateTeam: (id: string, team: TeamInput) =>
    request<Team>(`/company/teams/${id}`, json('PUT', team)),
  deleteTeam: (id: string) => request<void>(`/company/teams/${id}`, { method: 'DELETE' }),
  addMembers: (teamId: string, people: PersonInput[], roleId: string | null = null) =>
    request<MembersAdded>(
      `/company/teams/${teamId}/members`,
      json('POST', { people, role_id: roleId }),
    ),
  moveMembers: (memberIds: string[], teamId: string) =>
    request<Member[]>(
      '/company/members/move',
      json('POST', { member_ids: memberIds, team_id: teamId }),
    ),
  resetOverrides: (id: string) =>
    request<Member>(`/company/members/${id}/overrides`, { method: 'DELETE' }),
  draftRole: (teamId: string, role: Omit<RoleInput, 'spec'>) =>
    request<TeamDraft>(`/company/teams/${teamId}/roles/draft`, json('POST', role)),
  createRole: (teamId: string, role: RoleInput) =>
    request<Role>(`/company/teams/${teamId}/roles`, json('POST', role)),
  updateRole: (teamId: string, roleId: string, role: RoleInput) =>
    request<Role>(`/company/teams/${teamId}/roles/${roleId}`, json('PUT', role)),
  deleteRole: (teamId: string, roleId: string) =>
    request<void>(`/company/teams/${teamId}/roles/${roleId}`, { method: 'DELETE' }),
  patchProfiles: (teamId: string, target: PatchTarget, patch: ProfilePatch) =>
    request<{ changed: number }>(
      `/company/teams/${teamId}/patch`,
      json('POST', { ...target, patch }),
    ),
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

// The form of a company says nothing about it: «АО «Энергосеть»» is «Э».
const LEGAL_FORM = /^(ао|оао|зао|пао|ооо|гк|ук|фгуп|муп)\s+/i

/** The letters a company is known by, when it has no logo yet. */
export function companyInitials(name: string): string {
  const words = name
    .replace(/[«»"']/g, ' ')
    .trim()
    .replace(LEGAL_FORM, '')
    .split(/\s+/)
    .filter(Boolean)
  return (
    words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2)
  ).toUpperCase()
}
