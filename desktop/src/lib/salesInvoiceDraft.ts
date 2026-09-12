import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import {
  createSalesInvoiceDirect,
  fetchContacts,
  fetchContactTier,
  fetchCostCenters,
  fetchCreditStatus,
  fetchCurrencies,
  fetchLatestRate,
  fetchLoyaltySettings,
  fetchMembers,
  fetchSaleTypes,
  fetchStockLevels,
  newIdempotencyKey,
  resolvePrice,
  type ContactRecord,
  type CostCenterRecord,
  type CreditStatus,
  type Currency,
  type ResolvedPrice,
  type SaleType,
  type SalesInvoiceRecord,
  type StockLevel,
} from '../api'
import { isElectron } from '../platform'
import { todayIso } from './jalali'
import { usePersistentState } from './usePersistentState'

export interface DraftLine {
  itemId: string
  qty: string
  unitPrice: string
  discount: string
}

/**
 * منطقِ کاملِ «ثبتِ فاکتورِ فروش» — state، effectها، محاسبات و submit — در یک هوکِ
 * مشترک. هم فرمِ کلاسیک ([SalesInvoiceForm]) و هم ویزاردِ نسخه‌ی جدید ([SalesInvoiceWizard])
 * از این یک منبع می‌خوانند تا محاسباتِ مالی دوتکه/ناهم‌خوان نشود. رفتار دقیقاً همان
 * چیزی است که قبلاً درونِ فرم بود (رونوشت، تخفیفِ سطحِ باشگاه، اعتبار، ارز، idempotency).
 */
export function useSalesInvoiceDraft({
  token,
  warehouses,
  items,
  onQueued,
  prefill,
  onPrefillConsumed,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
  prefill?: SalesInvoiceRecord | null
  onPrefillConsumed?: () => void
}) {
  // در حالتِ رونوشت (prefill) پیش‌نویسِ ماندگار نباید بنشیند تا دیتای رونوشت را نیالاید.
  const persistOff = !!prefill
  const [warehouseId, setWarehouseId] = usePersistentState('cubita.draft.salesInvoice.warehouseId', '', persistOff)
  const [invoiceDate, setInvoiceDate] = usePersistentState('cubita.draft.salesInvoice.invoiceDate', todayIso(), persistOff)
  const [taxRate, setTaxRate] = usePersistentState('cubita.draft.salesInvoice.taxRate', '10', persistOff)
  const [invoiceDiscount, setInvoiceDiscount] = usePersistentState('cubita.draft.salesInvoice.invoiceDiscount', '', persistOff)
  const [invoiceDiscountMode, setInvoiceDiscountMode] = usePersistentState<'amount' | 'percent'>('cubita.draft.salesInvoice.invoiceDiscountMode', 'amount', persistOff)
  const [roundStep, setRoundStep] = usePersistentState('cubita.draft.salesInvoice.roundStep', 0, persistOff) // ۰ = بدون رند
  const [lines, setLines] = usePersistentState<DraftLine[]>('cubita.draft.salesInvoice.lines', [{ itemId: '', qty: '1', unitPrice: '', discount: '' }], persistOff)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [costCenterId, setCostCenterId] = usePersistentState('cubita.draft.salesInvoice.costCenterId', '', persistOff)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = usePersistentState('cubita.draft.salesInvoice.contactId', '', persistOff)
  const [brokerId, setBrokerId] = usePersistentState('cubita.draft.salesInvoice.brokerId', '', persistOff)
  //: فروشنده کاربرِ سامانه است نه طرف‌حساب — مبنای «محاسبه پورسانت».
  const [salespeople, setSalespeople] = useState<{ id: string; name: string }[]>([])
  const [salespersonId, setSalespersonId] = usePersistentState('cubita.draft.salesInvoice.salespersonId', '', persistOff)
  const [saleTypes, setSaleTypes] = useState<SaleType[]>([])
  const [saleTypeId, setSaleTypeId] = usePersistentState('cubita.draft.salesInvoice.saleTypeId', '', persistOff)
  const [credit, setCredit] = useState<CreditStatus | null>(null)
  // تخفیفِ خودکارِ سطحِ باشگاه (اگر در تنظیماتِ باشگاه فعال باشد).
  const [tierAuto, setTierAuto] = useState(false)
  const [autoTier, setAutoTier] = useState<{ name: string; pct: number } | null>(null)
  const autoTierActiveRef = useRef(false)
  const suppressTierRef = useRef(false)
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [currencyCode, setCurrencyCode] = useState('')
  const [exchangeRate, setExchangeRate] = useState('1')
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])

  // موجودیِ انبار زنده خوانده می‌شود تا کاربر *قبل از* ثبت، کسری را ببیند —
  // نه اینکه بعد از ثبت خطای ۴۰۰ بگیرد. آفلاین که نشد، ستون خالی می‌ماند.
  useEffect(() => {
    fetchStockLevels(token)
      .then(setStockLevels)
      .catch(() => setStockLevels([]))
  }, [token])

  // کلید یکتاسازی به *این فاکتور* گره می‌خورد، نه به هر تلاش شبکه‌ای. اگر ثبت با خطا
  // برگردد و کاربر دوباره بزند، همان کلید می‌رود (شاید سرور نوبت اول کارش را کرده و
  // فقط پاسخ گم شده). کلید فقط بعد از موفقیتِ قطعی نو می‌شود.
  const idempotencyKey = useRef(newIdempotencyKey())

  // رونوشتِ فاکتور: با تغییرِ prefill، فرم با اقلامِ همان فاکتور به‌عنوان پیش‌نویسِ تازه
  // پر می‌شود. تخفیفِ سطری عیناً منتقل می‌شود (که سهمِ تخفیفِ کل را هم دارد)، پس تخفیفِ
  // کل و رند صفر می‌مانند تا دوبار حساب نشود. تاریخ و کلیدِ یکتاسازی تازه‌اند.
  useEffect(() => {
    if (!prefill) return
    setWarehouseId(prefill.warehouse_id)
    // رونوشت: تخفیفِ سطح را روی این فاکتور اعمال نکن (تخفیفِ سطری از فاکتورِ اصلی می‌آید).
    suppressTierRef.current = true
    setContactId(prefill.contact_id ?? '')
    setTaxRate(String(Number(prefill.tax_rate)))
    setCurrencyCode('')
    setInvoiceDiscount('')
    setRoundStep(0)
    setInvoiceDate(todayIso())
    setLines(
      prefill.lines.map((l) => ({
        itemId: l.item_id,
        qty: String(Number(l.qty)),
        unitPrice: String(Number(l.unit_price)),
        discount: Number(l.discount) ? String(Number(l.discount)) : '',
      })),
    )
    idempotencyKey.current = newIdempotencyKey()
    setMessage(`رونوشت از فاکتور شماره ${prefill.number ?? ''} بارگذاری شد؛ ویرایش و ثبت کنید.`)
    onPrefillConsumed?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill])

  // مراکز هزینه زنده خوانده می‌شوند؛ آفلاین که نشد، انتخاب‌گر پنهان و فاکتور بدون مرکز است.
  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [token])

  // فروشنده و نوعِ فروش، همان الگوی مراکز هزینه: زنده، و آفلاین که نشد پنهان.
  // نوعِ غیرفعال کنار می‌رود چون سرور هم ردش می‌کند.
  useEffect(() => {
    fetchMembers(token)
      .then((r) => setSalespeople(r.members.map((m) => ({ id: m.user_id, name: m.name || m.email }))))
      .catch(() => setSalespeople([]))
    fetchSaleTypes(token)
      .then((rows) => setSaleTypes(rows.filter((t) => t.is_active)))
      .catch(() => setSaleTypes([]))
  }, [token])

  // مشتری‌ها هم زنده خوانده می‌شوند (همان الگوی مراکز هزینه). تأمین‌کننده‌ها کنار می‌روند.
  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'supplier')))
      .catch(() => setContacts([]))
  }, [token])

  // ارزها زنده خوانده می‌شوند؛ آفلاین که نشد، انتخاب‌گر پنهان و فاکتور به ریال است.
  useEffect(() => {
    fetchCurrencies(token)
      .then(setCurrencies)
      .catch(() => setCurrencies([]))
  }, [token])

  // با انتخابِ ارز، آخرین نرخِ ثبت‌شده پیشنهاد می‌شود (کاربر می‌تواند دستی تغییر دهد).
  useEffect(() => {
    if (!currencyCode) {
      setExchangeRate('1')
      return
    }
    let cancelled = false
    fetchLatestRate(token, currencyCode)
      .then((r) => !cancelled && r.rate && setExchangeRate(String(Number(r.rate))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, currencyCode])

  // وضعیت اعتبارِ مشتریِ انتخاب‌شده را زنده می‌گیریم تا مانده و سقف را نشان دهیم.
  useEffect(() => {
    if (!contactId) {
      setCredit(null)
      return
    }
    let cancelled = false
    fetchCreditStatus(token, contactId)
      .then((s) => !cancelled && setCredit(s))
      .catch(() => !cancelled && setCredit(null))
    return () => {
      cancelled = true
    }
  }, [token, contactId])

  // آیا «پیشنهادِ خودکارِ تخفیفِ سطح» در تنظیماتِ باشگاه روشن است؟
  useEffect(() => {
    fetchLoyaltySettings(token)
      .then((s) => setTierAuto(!!s.tier_discount_auto))
      .catch(() => {})
  }, [token])

  function applyAutoTier(v: { name: string; pct: number } | null) {
    setAutoTier(v)
    autoTierActiveRef.current = v != null
  }

  // با انتخابِ مشتری، تخفیفِ سطحش را (اگر داشته باشد) روی تخفیفِ کلِ فاکتور می‌نشانیم؛
  // با عوض/برداشتنِ مشتری هم اگر تخفیف از سطح آمده بود پاکش می‌کنیم. (روی رونوشت نه.)
  useEffect(() => {
    if (suppressTierRef.current) {
      suppressTierRef.current = false
      return
    }
    if (!tierAuto) return
    if (!contactId) {
      if (autoTierActiveRef.current) {
        setInvoiceDiscount('')
        applyAutoTier(null)
      }
      return
    }
    let cancelled = false
    fetchContactTier(token, contactId)
      .then((t) => {
        if (cancelled) return
        const pct = Number(t.discount_percent) || 0
        if (t.tier_name && pct > 0) {
          setInvoiceDiscountMode('percent')
          setInvoiceDiscount(String(pct))
          applyAutoTier({ name: t.tier_name, pct })
        } else if (autoTierActiveRef.current) {
          setInvoiceDiscount('')
          applyAutoTier(null)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, contactId, tierAuto])

  // ── قیمت از اعلامیه، با **همه‌ی** زمینه‌اش (§۵۳ §۵۴ §۹۲) ──────────────
  //
  // تا پیش از فصلِ «اعلامیه قیمت» این‌جا یک نگاشتِ محلیِ `item_id → price` ساخته
  // می‌شد از `contact.default_price_list_id` — ستونی که حل‌کننده‌ی سرور اصلاً
  // نگاهش نمی‌کند. آن نگاشت نه تاریخِ اجرا را می‌دید، نه فعال‌بودنِ اعلامیه را، و
  // نه نوعِ فروش/واحد/گروهِ مشتری/ارز را؛ و چند ردیفِ یک کالا را دلبخواه به یکی
  // فرو می‌ریخت. نتیجه این بود که فرم یک قیمت پر می‌کرد و `assert_within_policy`
  // با قاعده‌ی **دیگری** اعتبارش را می‌سنجید — پس اولین اعلامیه‌ای که حدِ واقعی
  // می‌گذاشت، قیمتی را رد می‌کرد که خودِ فرم پر کرده بود.
  const priceContext = useMemo(
    () => ({
      saleTypeId: saleTypeId || null,
      contactId: contactId || null,
      currencyCode: currencyCode || 'IRR',
      on: invoiceDate,
    }),
    [saleTypeId, contactId, currencyCode, invoiceDate],
  )
  const contextKey = `${priceContext.saleTypeId}|${priceContext.contactId}|${priceContext.currencyCode}|${priceContext.on}`

  // نرخِ مصوب و حدهای هر کالا، برای نمایش کنارِ ردیف. با عوض‌شدنِ زمینه دور
  // ریخته می‌شود، چون دیگر جوابِ همان پرسش نیست.
  const [priceInfo, setPriceInfo] = useState<Record<string, ResolvedPrice | null>>({})
  const priceInfoRef = useRef(priceInfo)
  priceInfoRef.current = priceInfo
  useEffect(() => {
    // ref هم همین‌جا پاک می‌شود، نه در رندرِ بعدی: وگرنه یک `resolveFor` که
    // بلافاصله پس از تغییرِ زمینه صدا زده شود، جوابِ زمینه‌ی قبلی را از کش می‌دهد.
    priceInfoRef.current = {}
    setPriceInfo({})
  }, [contextKey])

  const resolveFor = useCallback(
    async (itemId: string): Promise<ResolvedPrice | null> => {
      if (itemId in priceInfoRef.current) return priceInfoRef.current[itemId]
      let got: ResolvedPrice | null = null
      try {
        got = await resolvePrice(token, itemId, priceContext)
      } catch {
        got = null // آفلاین یا خطا: به قیمتِ پایه برمی‌گردیم، مثلِ همیشه
      }
      priceInfoRef.current = { ...priceInfoRef.current, [itemId]: got }
      setPriceInfo(priceInfoRef.current)
      return got
    },
    [token, priceContext],
  )

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  // کالای خدماتی موجودیِ انبار ندارد (is_service در کش عدد ۰/۱ است).
  function isService(itemId: string): boolean {
    return !!items.find((it) => it.id === itemId)?.is_service
  }

  // موجودیِ در دسترسِ یک کالا در انبارِ انتخاب‌شده (null یعنی نامشخص/خدماتی).
  function availableStock(itemId: string): number | null {
    if (!itemId || !effectiveWarehouseId || isService(itemId)) return null
    const row = stockLevels.find((s) => s.item_id === itemId && s.warehouse_id === effectiveWarehouseId)
    return row ? Number(row.qty) : 0
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  /** قیمتِ پایه‌ی کالا — وقتی هیچ قاعده‌ای با این زمینه نمی‌خواند (§۵۸). */
  function basePrice(itemId: string): number {
    const it = items.find((x) => x.id === itemId)
    return it ? Number(it.sales_price) : 0
  }

  // انتخابِ کالا در یک ردیف: فی از اعلامیه‌ی قیمت پر می‌شود، وگرنه قیمتِ پایه.
  function chooseLineItem(index: number, itemId: string) {
    if (!itemId) {
      updateLine(index, { itemId: '', unitPrice: '' })
      return
    }
    updateLine(index, { itemId, unitPrice: '' })
    void resolveFor(itemId).then((rule) => {
      const price = rule ? Number(rule.unit_price) : basePrice(itemId)
      updateLine(index, { itemId, unitPrice: price ? String(price) : '' })
    })
  }

  /**
   * تغییرِ نوعِ فروش **می‌پرسد**، بی‌صدا قیمت‌ها را بازنویسی نمی‌کند (§۷ §۸ §۹۵).
   *
   * نوعِ فروش یکی از ابعادِ قیمت است، پس عوض‌کردنش یعنی قیمتِ ردیف‌های موجود
   * ممکن است دیگر آن چیزی نباشد که اعلامیه می‌گوید. ولی قیمتِ روی ردیف شاید
   * نتیجه‌ی یک توافقِ تجاری باشد؛ بازنویسیِ خاموشش به‌عنوانِ عارضه‌ی جانبیِ یک
   * setter، تصمیمِ کاربر را از او می‌گیرد.
   *
   * پرسش این‌جاست و نه در فرم/ویزارد، چون هر دو از همین هوک می‌آیند و دو
   * پیاده‌سازیِ جدا دیر یا زود از هم جدا می‌افتند.
   */
  function changeSaleType(next: string) {
    setSaleTypeId(next)
    const priced = lines.filter((l) => l.itemId && Number(l.unitPrice) > 0)
    if (priced.length === 0) return
    const ok = window.confirm('آیا مایلید فی با توجه به نوعِ فروشِ جدید تغییر یابد؟')
    if (!ok) return
    void repriceAll({ ...priceContext, saleTypeId: next || null })
  }

  /** هر ردیفِ قیمت‌خورده را با زمینه‌ی تازه دوباره حل می‌کند. */
  async function repriceAll(ctx: typeof priceContext) {
    const targets = [...new Set(lines.filter((l) => l.itemId).map((l) => l.itemId))]
    const resolved = new Map<string, ResolvedPrice | null>()
    await Promise.all(
      targets.map(async (id) => {
        try {
          resolved.set(id, await resolvePrice(token, id, ctx))
        } catch {
          resolved.set(id, null)
        }
      }),
    )
    priceInfoRef.current = Object.fromEntries(resolved)
    setPriceInfo(priceInfoRef.current)
    setLines((prev) =>
      prev.map((line) => {
        if (!line.itemId) return line
        const rule = resolved.get(line.itemId)
        // قاعده‌ای نبود یعنی سیاستی نیست که اعمال شود — قیمتِ ردیف دست‌نخورده می‌ماند.
        if (!rule) return line
        return { ...line, unitPrice: String(Number(rule.unit_price)) }
      }),
    )
  }

  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitPrice: '', discount: '' }])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const gross = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitPrice) || 0), 0)
  const discountTotal = lines.reduce((sum, line) => sum + (Number(line.discount) || 0), 0)
  // خالصِ پس از تخفیفِ سطری.
  const netAfterLine = gross - discountTotal
  // تخفیفِ کلِ فاکتور: مبلغی یا درصدی (روی خالصِ پس از تخفیفِ سطری). سقفش همان خالص است.
  const invoiceDiscountInput = Number(invoiceDiscount) || 0
  const invoiceDiscountAmount = Math.min(
    invoiceDiscountMode === 'percent' ? Math.round((netAfterLine * invoiceDiscountInput) / 100) : invoiceDiscountInput,
    netAfterLine,
  )
  // پایه‌ی مالیات، خالصِ پس از همه‌ی تخفیف‌هاست — همان چیزی که سرور هم حساب می‌کند.
  const total = netAfterLine - invoiceDiscountAmount
  const taxRateNum = Math.min(Math.max(Number(taxRate) || 0, 0), 100)
  const taxAmount = Math.round((total * taxRateNum) / 100)
  const grandBeforeRound = total + taxAmount
  // رند فقط به پایین (به نفعِ مشتری) و فقط در ریالِ پایه معنا دارد؛ در ارز پنهان است.
  const roundAdjust = roundStep > 0 && !currencyCode ? Math.floor(grandBeforeRound / roundStep) * roundStep - grandBeforeRound : 0
  const grandTotal = grandBeforeRound + roundAdjust
  // ارز پایه = ریال با نرخ ۱. مبالغِ بالا به ارزِ انتخابی وارد شده‌اند؛ برای ارسال و
  // نمایشِ معادلِ ریالی در نرخ ضرب می‌شوند. دفتر همیشه ریالی است.
  const rate = currencyCode ? Number(exchangeRate) || 1 : 1
  const baseGrandTotal = Math.round(grandTotal * rate)

  //: لیستِ سیاه فقط هشدار می‌دهد و ثبت را نمی‌بندد — گاهی آگاهانه و موقتاً برای
  //: همان شخص فاکتور می‌زنیم. از خودِ رکوردِ طرف‌حساب خوانده می‌شود، نه از یک
  //: درخواستِ جدا: فهرست از قبل این‌جاست و نمای دومِ همان داده نمی‌سازیم.
  const blacklisted = contacts.some((c) => c.id === contactId && c.is_blacklisted)

  //: فقط طرف‌حساب‌هایی که واقعاً نقشِ «واسط» دارند. سرور هم همین را می‌سنجد؛
  //: این‌جا فقط جلوی انتخابِ نشدنی گرفته می‌شود.
  const brokers = contacts.filter((c) => c.is_broker)
  //: **پیش‌نمایش** است نه مقدارِ ذخیره‌شونده. عددِ قطعی را سرور در لحظه‌ی ثبت قفل
  //: می‌کند؛ این فقط می‌گوید «حدوداً چقدر می‌شود» تا کاربر پیش از ثبت ببیند.
  const brokerCommission = (() => {
    const b = brokers.find((c) => c.id === brokerId)
    if (!b) return null
    const pct = Number(b.commission_rate) || 0
    if (!(pct > 0)) return { name: b.name, pct: 0, amount: 0 }
    return { name: b.name, pct, amount: Math.round((total * pct) / 100) }
  })()

  //: «جلوگیری کن» در فرمِ طرف حساب باید واقعاً جلو بگیرد — تا امروز ذخیره
  //: می‌شد و هیچ اثری نداشت. تصمیم این‌جا گرفته می‌شود، در لحظه‌ی فروش، نه سرِ
  //: همگام‌سازیِ آفلاین که فروش قبلاً انجام شده. سرور هم همین گارد را دارد؛
  //: این‌جا فقط زودتر و با پیامِ روشن‌تر می‌گوید.
  const creditBlock = (() => {
    const contact = contacts.find((c) => c.id === contactId)
    if (!contact || contact.credit_action !== 'block' || !credit) return null
    const limit = Number(credit.credit_limit)
    //: سقفِ صفر یعنی «بدون سقف» — همان قاعده‌ی سرور.
    if (!(limit > 0)) return null
    const projected = Number(credit.outstanding) + baseGrandTotal
    return projected > limit ? { projected, limit, name: contact.name } : null
  })()

  // اعتبارسنجیِ آماده‌ی ثبت (برای گِیتِ مرحله‌ی ویزارد و پیامِ فرم).
  const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
  const overDiscountLine = validLines.find(
    (l) => (Number(l.discount) || 0) > (Number(l.qty) || 0) * (Number(l.unitPrice) || 0),
  )
  const linesValid = validLines.length > 0 && !overDiscountLine

  /** فاکتور را ثبت (یا در صفِ آفلاین) می‌کند. true اگر موفق. پیام را خودش ست می‌کند. */
  async function submit(): Promise<boolean> {
    setMessage(null)

    if (!effectiveWarehouseId) {
      setMessage('ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.')
      return false
    }
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return false
    }
    if (overDiscountLine) {
      setMessage('تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد.')
      return false
    }

    const payload = {
      invoice_date: invoiceDate,
      warehouse_id: effectiveWarehouseId,
      tax_rate: taxRateNum,
      cost_center_id: costCenterId || null,
      contact_id: contactId || null,
      broker_id: brokerId || null,
      salesperson_id: salespersonId || null,
      sale_type_id: saleTypeId || null,
      currency_code: currencyCode || null,
      exchange_rate: rate,
      // مبالغ به پایه (ریال) تبدیل می‌شوند؛ دفتر همیشه پایه است.
      invoice_discount: Math.round(invoiceDiscountAmount * rate),
      rounding: Math.round(roundAdjust * rate),
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        qty: Number(l.qty),
        unit_price: Math.round((Number(l.unitPrice) || 0) * rate),
        discount: Math.round((Number(l.discount) || 0) * rate),
      })),
    }

    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queueSalesInvoice(payload)
        setMessage('فاکتور در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createSalesInvoiceDirect(token, payload, idempotencyKey.current)
        setMessage('فاکتور با موفقیت ثبت شد.')
      }
      idempotencyKey.current = newIdempotencyKey() // فاکتور بعدی، کلید تازه
      setLines([{ itemId: '', qty: '1', unitPrice: '', discount: '' }])
      setCostCenterId('')
      setContactId('')
      setBrokerId('')
      setSalespersonId('')
      setSaleTypeId('')
      setCurrencyCode('')
      setInvoiceDiscount('')
      setRoundStep(0)
      onQueued()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    // state + setters
    warehouseId,
    setWarehouseId,
    effectiveWarehouseId,
    invoiceDate,
    setInvoiceDate,
    taxRate,
    setTaxRate,
    taxRateNum,
    invoiceDiscount,
    setInvoiceDiscount,
    invoiceDiscountMode,
    setInvoiceDiscountMode,
    invoiceDiscountAmount,
    roundStep,
    setRoundStep,
    roundAdjust,
    lines,
    updateLine,
    chooseLineItem,
    addLine,
    removeLine,
    costCenters,
    costCenterId,
    setCostCenterId,
    contacts,
    contactId,
    setContactId,
    credit,
    blacklisted,
    creditBlock,
    brokers,
    brokerId,
    setBrokerId,
    brokerCommission,
    salespeople,
    salespersonId,
    setSalespersonId,
    saleTypes,
    saleTypeId,
    //: فرم و ویزارد همین را صدا می‌زنند؛ پرسشِ «فی تغییر کند؟» داخلش است.
    setSaleTypeId: changeSaleType,
    priceInfo,
    autoTier,
    currencies,
    currencyCode,
    setCurrencyCode,
    exchangeRate,
    setExchangeRate,
    isService,
    availableStock,
    // derived
    gross,
    discountTotal,
    netAfterLine,
    total,
    taxAmount,
    grandTotal,
    baseGrandTotal,
    linesValid,
    // status + actions
    message,
    setMessage,
    submitting,
    submit,
  }
}

export type SalesInvoiceDraft = ReturnType<typeof useSalesInvoiceDraft>
