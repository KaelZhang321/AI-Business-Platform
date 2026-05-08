import { GripVertical, X } from 'lucide-react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

interface SortableItemProps {
  id: string
  content: string
  onRemove: (id: string) => void
  colorClass: string
  handleColorClass: string
}

export const SortableItem = ({ id, content, onRemove, colorClass, handleColorClass }: SortableItemProps) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center justify-between p-3 mb-3 bg-white dark:bg-slate-800 rounded-xl border shadow-sm group cursor-target ${colorClass}`}
    >
      <div className="flex items-center flex-1 min-w-0">
        <div
          {...attributes}
          {...listeners}
          className={`cursor-grab active:cursor-grabbing p-1 mr-2 ${handleColorClass}`}
        >
          <GripVertical className="w-4 h-4" />
        </div>
        <span className="text-sm text-slate-700 dark:text-slate-200 truncate">{content}</span>
      </div>
      <button
        onClick={() => onRemove(id)}
        className="w-6 h-6 flex items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  )
}
