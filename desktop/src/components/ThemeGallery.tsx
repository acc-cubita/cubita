import { Check, Palette, PanelsTopLeft, PanelRight } from 'lucide-react'
import { useTheme } from '../lib/theme'
import { PageHeader } from './PageHeader'

/** بخشِ «ظاهر و پوسته» — گالریِ کارت‌های تم با پیش‌نمایشِ کوچکِ رنگ+چیدمان. انتخاب
 *  بلافاصله اعمال و در localStorage ذخیره می‌شود. افزودنِ تمِ تازه فقط با یک ردیف در
 *  رجیستریِ THEMES و یک بلوکِ توکن در index.css انجام می‌شود — این صفحه خودکار نشانش می‌دهد. */
export function ThemeGallery() {
  const { theme, themes, setThemeId } = useTheme()
  return (
    <div className="page">
      <PageHeader
        icon={Palette}
        title="ظاهر و پوسته"
        description="پوسته‌ی برنامه را انتخاب کنید؛ رنگ‌ها و چیدمان بلافاصله اعمال و برای دفعاتِ بعد ذخیره می‌شوند."
      />
      <div className="theme-gallery">
        {themes.map((t) => {
          const selected = t.id === theme.id
          return (
            <button
              key={t.id}
              type="button"
              className={`theme-card${selected ? ' selected' : ''}`}
              onClick={() => setThemeId(t.id)}
              aria-pressed={selected}
            >
              <div className="theme-card-preview" data-shell={t.shell}>
                <div className="tp-nav" style={{ background: t.swatches[0] }}>
                  <span className="tp-dot" style={{ background: t.swatches[1] }} />
                  <span className="tp-line" />
                  <span className="tp-line" />
                </div>
                <div className="tp-body" style={{ background: t.kind === 'dark' ? '#1f1f1f' : '#eef0f3' }}>
                  <span className="tp-panel" style={{ background: t.swatches[2] }} />
                  <span className="tp-btn" style={{ background: t.swatches[1] }} />
                </div>
              </div>
              <div className="theme-card-body">
                <div className="theme-card-title">
                  <span>{t.label}</span>
                  {selected && <Check size={16} className="theme-check" />}
                </div>
                <div className="theme-card-meta">
                  {t.shell === 'topnav' ? (
                    <span className="theme-tag">
                      <PanelsTopLeft size={13} /> نوارِ افقی
                    </span>
                  ) : (
                    <span className="theme-tag">
                      <PanelRight size={13} /> نوارِ کناری
                    </span>
                  )}
                  <span className="theme-tag">{t.kind === 'dark' ? 'تیره' : 'روشن'}</span>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
