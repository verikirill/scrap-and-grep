/** What a dragged member row carries: the ids of the people being moved, as JSON. */
export const DRAG_TYPE = 'application/x-radar-members'

/** The people a drop brings, or none when something else was dropped. */
export function droppedMembers(data: DataTransfer): string[] {
  try {
    const ids: unknown = JSON.parse(data.getData(DRAG_TYPE) || '[]')
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}
