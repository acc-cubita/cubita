import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Search } from 'lucide-react'
import type { MeResponse } from '../api'
import { buildNav, uniqueNavItems, type PageKey } from '../lib/navModel'
import { TASK_LAUNCHERS } from '../lib/taskRegistry'

interface Command {
  id: string
  title: string
  subtitle?: string
  keywords: string
  icon: ReactNode
  page: PageKey
  section?: string
  kind: 'task' | 'page'
}

/**
 * کامندپالتِ سراسری (Ctrl/⌘+K) برای «نسخه‌ی جدید» — پرش به هر صفحه یا شروعِ یک کار.
 * منبعِ فرمان‌ها همان navModel + taskRegistry است تا با منو یکی بماند. فقط پوسته‌ی guided.
 */
export function CommandPalette({ me, onNavigate }: { me: MeResponse; onNavigate: (page: PageKey, section: string | null) => void }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  // Ctrl/⌘+K برای باز/بسته؛ Escape برای بستن. سراسری تا از هر جای برنامه در دسترس باشد.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => !o)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const commands = useMemo<Command[]>(() => {
    const { groups, secondary } = buildNav({
      isPlatformAdmin: me.is_platform_admin,
      isSuperAdmin: me.is_super_admin,
      tenantKind: me.tenant_kind,
      enabledModules: me.enabled_modules,
      allowedModules: me.allowed_modules,
      isOwner: me.role_key === 'owner',
    })
    const tasks: Command[] = TASK_LAUNCHERS.map((t) => ({
      id: `task-${t.key}`,
      title: t.title,
      subtitle: t.desc,
      keywords: `${t.title} ${t.desc}`,
      icon: <t.icon size={16} />,
      page: t.page,
      section: t.section,
      kind: 'task',
    }))
    const pageItems = uniqueNavItems(groups, secondary)
    const pages: Command[] = pageItems.map((it) => ({
      id: `page-${it.key}`,
      title: it.label,
      subtitle: 'رفتن به صفحه',
      keywords: it.label,
      icon: it.icon,
      page: it.key,
      kind: 'page',
    }))
    return [...tasks, ...pages]
  }, [me])

  const filtered = useMemo(() => {
    const q = query.trim()
    if (!q) return commands
    return commands.filter((c) => c.keywords.includes(q))
  }, [commands, query])

  useEffect(() => {
    setActive(0)
  }, [query, open])

  useEffect(() => {
    if (open) {
      setQuery('')
      // فوکوس بعد از mount شدنِ ورودی
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  // آیتمِ فعال همیشه در دید بماند (پیمایش با کلید)
  useEffect(() => {
    listRef.current?.querySelector('.cmdk-item.is-active')?.scrollIntoView({ block: 'nearest' })
  }, [active])

  if (!open) return null

  function run(c: Command) {
    onNavigate(c.page, c.section ?? null)
    setOpen(false)
  }

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const c = filtered[active]
      if (c) run(c)
    }
  }

  return (
    <div className="cmdk-overlay" onMouseDown={() => setOpen(false)}>
      <div className="cmdk" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="جست‌وجوی فرمان">
        <div className="cmdk-search">
          <Search size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="برو به… یا یک کار را شروع کن (مثلاً «فاکتور فروش»)"
            aria-label="جست‌وجو"
          />
          <kbd className="cmdk-esc">Esc</kbd>
        </div>
        <ul className="cmdk-list" ref={listRef}>
          {filtered.length === 0 ? (
            <li className="cmdk-empty">چیزی پیدا نشد</li>
          ) : (
            filtered.map((c, i) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`cmdk-item${i === active ? ' is-active' : ''}`}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(c)}
                >
                  <span className="cmdk-item-icon">{c.icon}</span>
                  <span className="cmdk-item-text">
                    <span className="cmdk-item-title">{c.title}</span>
                    {c.subtitle && <span className="cmdk-item-sub">{c.subtitle}</span>}
                  </span>
                  <span className={`cmdk-item-kind is-${c.kind}`}>{c.kind === 'task' ? 'شروعِ کار' : 'صفحه'}</span>
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="cmdk-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> جابه‌جایی</span>
          <span><kbd>↵</kbd> انتخاب</span>
          <span><kbd>Ctrl</kbd>+<kbd>K</kbd> باز/بسته</span>
        </div>
      </div>
    </div>
  )
}
