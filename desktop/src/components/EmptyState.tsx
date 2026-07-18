import type { LucideIcon } from 'lucide-react'

export function EmptyState({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <div className="empty-state">
      <Icon size={22} />
      <p>{text}</p>
    </div>
  )
}
