import { AbilityBuilder, createMongoAbility, MongoAbility } from '@casl/ability'

type Actions = 'manage' | 'read' | 'create' | 'update' | 'delete'
type Subjects = 'Task' | 'Document' | 'Audit' | 'Conversation' | 'User' | 'all'

export type AppAbility = MongoAbility<[Actions, Subjects]>

export function defineAbilityFor(role: string): AppAbility {
  const { can, build } = new AbilityBuilder<AppAbility>(createMongoAbility)

  switch (role) {
    case 'admin':
      can('manage', 'all')
      break
    case 'user':
      can('read', 'Task')
      can('read', 'Document')
      can('create', 'Document')
      can('read', 'Conversation')
      can('create', 'Conversation')
      break
    case 'viewer':
      can('read', 'Task')
      can('read', 'Document')
      can('read', 'Conversation')
      break
    default:
      // no permissions
      break
  }

  return build()
}
