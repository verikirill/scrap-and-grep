import { toast } from '../../lib/toast'
import { inviteUrl } from '../../lib/company'
import type { Member } from '../../lib/company'

/** Put text on the clipboard and say so; false where the browser refuses. */
export async function copyText(text: string, done: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(done)
    return true
  } catch {
    // No clipboard outside HTTPS: the caller shows the text to copy by hand.
    toast.error('Браузер не дал скопировать. Выделите ссылку и скопируйте её вручную.')
    return false
  }
}

/** «Анна Смирнова: https://…/invite/…», one person a line, ready for a chat or a mail. */
export function invitationsText(members: Pick<Member, 'display_name' | 'invite_path'>[]): string {
  return members
    .map((member) => {
      const url = inviteUrl(member)
      return url ? `${member.display_name}: ${url}` : null
    })
    .filter(Boolean)
    .join('\n')
}
