// The digest page's second reader profile: written for management, so its
// issues cover a week and its schedule suggests Monday mornings. With
// makeProfile() (profile-1, a specialist's) it makes a choice of two.
import type { Profile } from '../../lib/api'
import { makeInterests, makeProfile, makeSpec } from './profiles'

export function makeManagementProfile(overrides: Partial<Profile> = {}): Profile {
  return makeProfile({
    id: 'profile-2',
    spec: makeSpec({
      name: 'Руководство ИБ',
      role: 'Руководитель службы ИБ',
      audience: 'management',
      interests: makeInterests(3),
    }),
    defaults: { period_days: 7, schedule: { cadence: 'weekly', weekday: 0, time: '09:00' } },
    ...overrides,
  })
}
