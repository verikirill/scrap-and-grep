import { useParams } from 'react-router'
import { SharedProfileDialog } from '../features/profiles/SharedProfileDialog'
import { DigestPage } from './DigestPage'

/** A profile link: the dialog opens over the digest page, where either answer leads. */
export function SharePage() {
  const { token = '' } = useParams()
  return (
    <>
      <DigestPage />
      <SharedProfileDialog token={token} />
    </>
  )
}
