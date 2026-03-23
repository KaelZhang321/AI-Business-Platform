import { createContext, type ReactNode, useContext } from 'react'

import type { AppAbility } from '../../abilities'

type Actions = 'manage' | 'read' | 'create' | 'update' | 'delete'
type Subjects = 'Task' | 'Document' | 'Audit' | 'Conversation' | 'User' | 'all'

export const AbilityContext = createContext<AppAbility>(undefined!)

interface CanProps {
  /** CASL action */
  I: Actions
  /** CASL subject */
  a: Subjects
  children: ReactNode
  /** Content shown when permission denied */
  fallback?: ReactNode
}

export function Can({ I: action, a: subject, children, fallback = null }: CanProps) {
  const ability = useContext(AbilityContext)
  return ability?.can(action, subject) ? <>{children}</> : <>{fallback}</>
}
