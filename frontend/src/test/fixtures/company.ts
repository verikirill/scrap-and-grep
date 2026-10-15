// A company space: a team of an energy company, its people and an invitation.
import type { Company, Invite, Member, Team } from '../../lib/company'
import { makeInterests, makeSpec } from './profiles'

export function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    id: 'member-1',
    display_name: 'Олег Смирнов',
    email: 'oleg@energo.example',
    job_title: 'Инженер SOC',
    avatar_preset: 'blue',
    team_id: 'team-1',
    audience: 'specialist',
    status: 'invited',
    invite_path: '/invite/oleg-link-0000000000000000000',
    invite_expires_at: '2026-10-30T09:00:00Z',
    last_login_at: null,
    created_at: '2026-10-16T09:00:00Z',
    ...overrides,
  }
}

export function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 'team-1',
    name: 'SOC',
    services: 'Круглосуточный мониторинг в MaxPatrol SIEM и разбор инцидентов.',
    spec: makeSpec({
      name: 'SOC',
      role: 'Команда «SOC» в компании «Энергосеть». Круглосуточный мониторинг.',
      interests: makeInterests(2),
      systems: ['MaxPatrol SIEM'],
    }),
    icon: 'shield',
    color: 'blue',
    members: [],
    created_at: '2026-10-16T09:00:00Z',
    updated_at: '2026-10-16T09:00:00Z',
    ...overrides,
  }
}

export function makeCompany(overrides: Partial<Company> = {}): Company {
  return {
    id: 'company-1',
    name: 'Энергосеть',
    about: 'Распределение электроэнергии в трёх регионах.',
    teams: [],
    created_at: '2026-10-16T09:00:00Z',
    ...overrides,
  }
}

export function makeInvite(overrides: Partial<Invite> = {}): Invite {
  return {
    display_name: 'Олег Смирнов',
    email: 'oleg@energo.example',
    company: 'Энергосеть',
    team: 'SOC',
    job_title: 'Инженер SOC',
    manager: 'Анна Петрова',
    audience: 'specialist',
    interests: ['Безопасность АСУ ТП', 'Уязвимости'],
    ...overrides,
  }
}
