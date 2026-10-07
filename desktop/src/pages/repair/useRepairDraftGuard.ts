import { useEffect, useRef, type FormEvent, type PointerEvent } from 'react'

/** Drafts and signatures stay in component memory; nothing is persisted. */
export function useRepairDraftGuard(register?: (guard: (() => boolean) | null) => void) {
 const root = useRef<HTMLDivElement>(null)
 const dirty = useRef(new Set<Element>())
 const focused = useRef<Element | null>(null)
 const actionScope = useRef<Element | null>(null)
 const hasChanges = () => [...dirty.current].some(element => root.current?.contains(element))
 const allowLeave = () => !hasChanges() || window.confirm('تغییرات ذخیره‌نشده دارید. از این بخش خارج شوید؟')
 useEffect(() => {
  const dirtyElements=dirty.current
  register?.(allowLeave)
  const beforeUnload = (event: BeforeUnloadEvent) => { if (hasChanges()) { event.preventDefault(); event.returnValue = '' } }
  window.addEventListener('beforeunload', beforeUnload)
  return () => { register?.(null); window.removeEventListener('beforeunload', beforeUnload); dirtyElements.clear() }
 }, [register])
 function change(event: FormEvent<HTMLDivElement>) {
  if (event.target instanceof Element && event.target.closest('[data-repair-draft]')) dirty.current.add(event.target)
 }
 function pointer(event: PointerEvent<HTMLDivElement>) {
  if (event.target instanceof HTMLCanvasElement) dirty.current.add(event.target)
 }
 function focus(target:EventTarget) { if(target instanceof Element && root.current?.contains(target) && target.closest('[data-repair-draft]')) focused.current=target.closest('.jalali-date-field')?.querySelector('.jalali-date-trigger')??target }
 function mark() { if(focused.current && root.current?.contains(focused.current)) dirty.current.add(focused.current) }
 function clicked(target: EventTarget) {
  if (target instanceof Element && target.closest('button')) actionScope.current = target.closest('details,form,[data-repair-action]')
 }
 function saved(scope: Element | null) {
  if (scope) for (const element of dirty.current) if (scope.contains(element)) dirty.current.delete(element)
 }
 return { root, change, pointer, focus, mark, clicked, saved, actionScope, allowLeave }
}
