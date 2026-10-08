import { RepairPanelActive } from './repairPanelActivity'
import { useId, useState, type ReactNode } from 'react'
export function RepairWorkspaceTabs({ label, value, tabs, onChange, panelIdPrefix }: { label: string; value: string; tabs: { id: string; label: string }[]; onChange: (id: string) => void; panelIdPrefix?:string }) {
 const generated = useId()
 const prefix = panelIdPrefix ?? generated
 return <div className="repair-workspace-tabs" role="tablist" aria-label={label}>{tabs.map((tab, index) => <button key={tab.id} id={`${prefix}-${tab.id}`} role="tab" aria-controls={panelIdPrefix?`${prefix}-panel-${tab.id}`:undefined} aria-selected={value === tab.id} tabIndex={value === tab.id ? 0 : -1} onClick={() => onChange(tab.id)} onKeyDown={event => {
 let next: number | undefined
 if (event.key === 'ArrowLeft') next = (index + 1) % tabs.length
 if (event.key === 'ArrowRight') next = (index + tabs.length - 1) % tabs.length
 if (event.key === 'Home') next = 0
 if (event.key === 'End') next = tabs.length - 1
 if (next !== undefined) { event.preventDefault(); onChange(tabs[next].id); document.getElementById(`${prefix}-${tabs[next].id}`)?.focus() }
 }}>{tab.label}</button>)}</div>
}
export function RepairRetainedPanel({ active, children, id, labelledBy }: { active: boolean; children: ReactNode;id?:string;labelledBy?:string }) {
 const [visited, setVisited] = useState(active)
 if (active && !visited) setVisited(true)
 return visited || active ? <RepairPanelActive.Provider value={active}><div role="tabpanel" id={id} aria-labelledby={labelledBy} hidden={!active}>{children}</div></RepairPanelActive.Provider> : null
}
