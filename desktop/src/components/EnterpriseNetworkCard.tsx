import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, ClipboardCopy, Network, RefreshCw, ShieldCheck } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { SearchSelect } from './SearchSelect'
import { NETWORK_TOPOLOGIES, editableNetworkAdapters, initialNetworkConfig, type NetworkConfig, type NetworkInventory, type NetworkPlan, type NetworkTopology } from '../lib/enterpriseNetwork'

export function EnterpriseNetworkCard() {
  const available = window.cubitaConfig?.edition === 'enterprise' && !!window.cubita?.networkInspect
  const [inventory, setInventory] = useState<NetworkInventory | null>(null)
  const [topology, setTopology] = useState<NetworkTopology | ''>('')
  const [config, setConfig] = useState<NetworkConfig | null>(null)
  const [manual, setManual] = useState(false)
  const [plan, setPlan] = useState<NetworkPlan | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState<'read' | 'preview' | 'apply' | 'disable' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!available) return
    setBusy('read'); setError(null); setPlan(null); setConfirmed(false)
    try {
      const r = await window.cubita.networkInspect!()
      if (!r.ok) { setError(r.error); return }
      setInventory(r.data)
      const saved = r.data.state.config
      if (saved) {
        setTopology(saved.topology)
        setConfig(initialNetworkConfig(r.data, saved.topology, saved.adapterId))
      } else setConfig(null)
    } catch (e) { setError(e instanceof Error ? e.message : 'کارت‌های شبکه خوانده نشدند؛ دوباره بررسی کنید.') }
    finally { setBusy(null) }
  }, [available])
  useEffect(() => { void refresh() }, [refresh])

  if (!available) return null
  const adapters = inventory && topology ? editableNetworkAdapters(inventory, topology) : []
  const adapter = inventory?.adapters.find((a) => a.id === config?.adapterId)
  const shared = topology !== 'direct'

  function patch(change: Partial<NetworkConfig>) {
    setConfig((old) => old ? { ...old, ...change } : old)
    setPlan(null); setConfirmed(false); setError(null); setMessage(null)
  }

  async function preview() {
    if (!config) return
    setBusy('preview'); setError(null); setPlan(null); setConfirmed(false)
    try {
      const r = await window.cubita.networkPreview!(config)
      if (r.ok) setPlan(r.data)
      else setError(r.error)
    } catch (e) { setError(e instanceof Error ? e.message : 'تغییرات بررسی نشدند؛ دوباره تلاش کنید.') }
    finally { setBusy(null) }
  }

  async function apply() {
    if (!plan || !confirmed || !config) return
    setBusy('apply'); setError(null)
    try {
      const r = await window.cubita.networkApply!(config)
      if (r.ok) { setMessage(r.data.message); await refresh() }
      else setError(r.error)
    } catch (e) { setError(e instanceof Error ? e.message : 'تنظیم شبکه اعمال نشد؛ دسترسی مدیر را بررسی کنید.') }
    finally { setBusy(null) }
  }

  async function disable() {
    if (!window.confirm('نگهداری خودکار و قاعدهٔ اختصاصی کوبیتا برداشته شود؟ IP موجود و اینترنت تغییر نمی‌کنند.')) return
    setBusy('disable'); setError(null)
    try {
      const r = await window.cubita.networkDisable!()
      if (r.ok) { setMessage(r.data.message); await refresh() }
      else setError(r.error)
    } catch (e) { setError(e instanceof Error ? e.message : 'غیرفعال‌سازی انجام نشد؛ دوباره تلاش کنید.') }
    finally { setBusy(null) }
  }

  async function copyUrl() {
    const url = inventory?.state.serverUrl
    if (!url) return
    try { await navigator.clipboard.writeText(url); setMessage('نشانی کپی شد؛ در کلاینت، صفحهٔ «اتصال به سرور» وارد کنید.') }
    catch { setError('کلیپ‌بورد در دسترس نیست؛ نشانی نمایش‌داده‌شده را دستی کپی کنید.') }
  }

  return (
    <SectionCard icon={Network} title="راه‌اندازی شبکهٔ داخلی" description="نوع ارتباط را انتخاب کنید؛ پیشنهاد خودکار یا تنظیم دستی، بدون بازنویسی تنظیمات اینترنت."
      actions={<button type="button" className="btn-secondary" onClick={refresh} disabled={busy !== null}><RefreshCw size={14} /> بررسی دوبارهٔ شبکه</button>}>
      <div className="enterprise-network">
        <p className="enterprise-network-safe"><ShieldCheck size={17} /> DNS، gateway، مسیر اینترنت، VPN و دسته‌بندی عمومی/خصوصی شبکه تغییر نمی‌کنند.</p>
        {busy === 'read' && <p className="muted" role="status">در حال خواندن کارت‌های این رایانه…</p>}
        {inventory && <>
          <p className="muted">نقش نصبِ این رایانه: {inventory.role === 'server' ? 'سرور' : 'کلاینت'} — این تنظیم فقط روی همین رایانه اعمال می‌شود.</p>
          <p className={inventory.state.enabled ? 'success' : 'muted'} role="status">{inventory.state.message}</p>
          {inventory.role === 'server' && inventory.state.enabled && inventory.state.serverUrl && <div className="enterprise-network-address">
            <span>نشانی اتصالِ کلاینت:</span><code dir="ltr">{inventory.state.serverUrl}</code>
            <button type="button" className="btn-secondary" onClick={copyUrl}><ClipboardCopy size={14} /> کپی نشانی</button>
          </div>}
          <div className="enterprise-network-fields">
            <label>نوع ارتباط
              <SearchSelect aria-label="نوع ارتباط شبکه" value={topology} disabled={busy !== null} onChange={(e) => {
                setTopology(e.target.value as NetworkTopology | ''); setConfig(null); setPlan(null); setConfirmed(false); setError(null)
              }}>
                <option value="">نوع ارتباط را انتخاب کنید</option>
                {NETWORK_TOPOLOGIES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </SearchSelect>
              {topology && <span className="field-hint">{NETWORK_TOPOLOGIES.find((o) => o.value === topology)?.hint}</span>}
            </label>
            {topology && <label>کارت شبکهٔ ارتباط با کلاینت/سرور
              <SearchSelect aria-label="کارت شبکه" value={config?.adapterId ?? ''} disabled={busy !== null} onChange={(e) => {
                setConfig(e.target.value ? initialNetworkConfig(inventory, topology, e.target.value) : null)
                setPlan(null); setConfirmed(false); setError(null)
              }}>
                <option value="">کارت این رایانه را انتخاب کنید</option>
                {adapters.map((a) => <option key={a.id} value={a.id}>{a.name} — {a.kind === 'wifi' ? 'بی‌سیم' : 'LAN'} — {a.status === 'Up' ? 'متصل' : 'قطع'}</option>)}
              </SearchSelect>
              {!adapters.length && <span className="field-hint">کارت فیزیکی مناسب پیدا نشد؛ کابل/Wi‑Fi و درایور را بررسی کنید.</span>}
            </label>}
          </div>
          {config && adapter && <>
            <div className="enterprise-network-facts">
              <span dir="ltr">{adapter.description}</span>
              <span>{adapter.defaultRoute ? 'دارای مسیر اینترنت — تغییر IP مجاز نیست' : 'بدون مسیر پیش‌فرض اینترنت'}</span>
              <span>دریافت IP: {adapter.dhcp ? 'خودکار (DHCP)' : 'دستی'}</span>
              <span>شبکه: {adapter.profile === 'Private' ? 'خصوصی' : adapter.profile === 'Public' ? 'عمومی' : adapter.profile === 'DomainAuthenticated' ? 'دامنه' : 'نامشخص'}</span>
            </div>
            <label className="enterprise-network-check"><input type="checkbox" checked={manual} disabled={busy !== null} onChange={(e) => {
              setManual(e.target.checked); setPlan(null); setConfirmed(false)
              if (!e.target.checked) setConfig(initialNetworkConfig(inventory, config.topology, config.adapterId))
            }} /> تنظیم دستی (IP، پیشوند و پورت)</label>
            <div className="enterprise-network-fields">
              <label>روش تنظیم IP
                <SearchSelect aria-label="روش تنظیم IP" value={config.mode} disabled={!manual || busy !== null} onChange={(e) => patch({ mode: e.target.value as 'keep' | 'static', staticConsent: false })}>
                  <option value="keep">حفظ IP و DHCP فعلی</option>
                  {!shared && !adapter.defaultRoute && <option value="static">IP ثابت روی کابل مستقیمِ جدا از اینترنت</option>}
                </SearchSelect>
              </label>
              <label>IP همین رایانه
                {config.mode === 'keep' ? <SearchSelect dir="ltr" aria-label="IP فعلی کارت" value={config.address} disabled={busy !== null} onChange={(e) => {
                  const a = adapter.addresses.find((item) => item.address === e.target.value)
                  if (a) patch({ address: a.address, prefix: a.prefix })
                }}><option value="">—</option>{adapter.addresses.map((a) => <option key={a.address} value={a.address}>{a.address}/{a.prefix}</option>)}</SearchSelect> :
                  <input dir="ltr" aria-label="IP همین رایانه" value={config.address} readOnly={!manual} disabled={busy !== null} onChange={(e) => patch({ address: e.target.value })} />}
                <span className="field-hint">سرور و کلاینت نباید یک IP داشته باشند؛ در کابل مستقیم محدودهٔ آن‌ها باید یکسان باشد.</span>
              </label>
              <label>طول پیشوند شبکه
                <input dir="ltr" aria-label="طول پیشوند شبکه" type="number" min={16} max={30} value={config.prefix} readOnly={!manual || config.mode === 'keep'} disabled={busy !== null} onChange={(e) => patch({ prefix: Number(e.target.value) })} />
                <span className="field-hint">۲۴ معادل ماسک 255.255.255.0 است.</span>
              </label>
              <label>پورت API سرور
                <input dir="ltr" aria-label="پورت سرور" type="number" min={1024} max={65535} value={config.port} readOnly={!manual} disabled={busy !== null} onChange={(e) => patch({ port: Number(e.target.value) })} />
                <span className="field-hint">باید با پورت نصب‌شدهٔ سرور برابر باشد؛ معمولاً ۸۴۲۰.</span>
              </label>
            </div>
            {config.mode === 'static' && <label className="enterprise-network-check"><input type="checkbox" checked={config.staticConsent} disabled={busy !== null} onChange={(e) => patch({ staticConsent: e.target.checked })} /> تأیید می‌کنم این کارت فقط برای کابل مستقیم است؛ DHCP فقط روی همین کارت خاموش شود.</label>}
            <label className="enterprise-network-check"><input type="checkbox" checked={config.startup} disabled={busy !== null} onChange={(e) => patch({ startup: e.target.checked })} /> نگهداری خودکار پس از روشن‌شدن و اتصال مجدد کابل (بررسی هر دقیقه)</label>
            <button type="button" className="btn-secondary" onClick={preview} disabled={busy !== null || !config.address || (config.mode === 'static' && !config.staticConsent)}>{busy === 'preview' ? 'در حال بررسی…' : 'بررسی تغییرات، بدون اعمال'}</button>
          </>}
          {plan && <div className="enterprise-network-preview">
            <h3>پیش‌نمایش تغییرات</h3>
            <p>کارت: <b>{plan.adapterName}</b> — {plan.addAddress ? 'افزودن IP ثابت' : 'حفظ IP فعلی'}</p>
            <p>محدودهٔ مجاز: <code dir="ltr">{plan.subnet}</code>؛ {inventory.role === 'server' ? 'فایروال فقط برای TCP همین پورت، کارت و محدوده باز می‌شود.' : 'روی کلاینت پورت ورودی باز نمی‌شود.'}</p>
            <ul>{plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            {inventory.role === 'client' && <p>در کابل مستقیم، IP این کلاینت را با محدودهٔ نشان‌داده‌شده روی سرور هماهنگ کنید؛ مثلاً اگر سرور .1 است، کلاینت .2 باشد. سپس در صفحهٔ اتصال، IP خود سرور را وارد کنید.</p>}
            <label className="enterprise-network-check"><input type="checkbox" checked={confirmed} disabled={busy !== null} onChange={(e) => setConfirmed(e.target.checked)} /> این کارت و محدوده، شبکهٔ داخلیِ مورد اعتماد من است؛ تغییرات بالا اعمال شوند.</label>
            <button type="button" className="btn-primary" onClick={apply} disabled={!confirmed || busy !== null}><CheckCircle2 size={15} /> {busy === 'apply' ? 'منتظر تأیید مدیر و اعمال شبکه…' : 'اعمال با تأیید مدیر ویندوز'}</button>
          </div>}
          {inventory.state.config && <button type="button" className="btn-secondary" onClick={disable} disabled={busy !== null}>برداشتن نگهداری خودکار و قاعدهٔ اختصاصی</button>}
        </>}
        {message && <p className="success" role="status">{message}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <p className="muted">در شبکهٔ مودم، IP ثابت را با رزرو DHCP در مودم تعیین کنید. برای تغییر gateway/DNS یا IP شبکهٔ مشترک از تنظیمات دستی ویندوز استفاده کنید؛ این برنامه آن‌ها را بازنویسی نمی‌کند.</p>
      </div>
    </SectionCard>
  )
}
