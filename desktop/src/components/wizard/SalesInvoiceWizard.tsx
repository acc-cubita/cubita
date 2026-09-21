import { useState } from 'react'
import { AlertTriangle, Plus, Trash2 } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../../electron.d'
import type { IssueInvoiceContext, SalesInvoiceRecord } from '../../api'
import { useSalesInvoiceDraft, type SalesInvoiceDraft } from '../../lib/salesInvoiceDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { ItemPicker } from '../ItemPicker'
import { PriceRuleHint } from '../PriceRuleHint'
import { CardPaymentButton } from '../CardPaymentDialog'
import { CreditBanner, SourceIssueBanner } from '../SalesInvoiceForm'
import { TaskFlow, type WizardStep } from './TaskFlow'
import { BlacklistBanner } from '../BlacklistBanner'
import { SearchSelect } from '../../components/SearchSelect'
import { FormField } from '../form/FormKit'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/**
 * ویزاردِ «ثبتِ فاکتورِ فروش» برای نسخه‌ی جدید (پوسته‌ی Tipalti). همان منطقِ فرمِ کلاسیک
 * ([useSalesInvoiceDraft]) را در چهار مرحله‌ی تاییدشونده می‌چیند، با پیش‌نمایشِ زنده‌ی سند
 * کنارِ صفحه. ثبتِ نهایی دقیقاً همان مسیرِ فعلی است (سرور یا صفِ آفلاین).
 */
export function SalesInvoiceWizard({
  token,
  warehouses,
  items,
  onQueued,
  prefill,
  onPrefillConsumed,
  issuePrefill,
  onIssuePrefillConsumed,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
  prefill?: SalesInvoiceRecord | null
  onPrefillConsumed?: () => void
  issuePrefill?: IssueInvoiceContext | null
  onIssuePrefillConsumed?: () => void
}) {
  const d = useSalesInvoiceDraft({
    token, warehouses, items, onQueued, prefill, onPrefillConsumed, issuePrefill, onIssuePrefillConsumed,
  })
  const [resetTick, setResetTick] = useState(0)

  if (warehouses.length === 0 || items.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">ثبت فاکتور فروش</h2>
        <p className="hint">قبل از ثبت فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
      </section>
    )
  }

  const steps: WizardStep[] = [
    {
      key: 'header',
      title: 'سربرگ و طرف‌حساب',
      subtitle: 'انبار، تاریخ و مشتریِ فاکتور را مشخص کنید.',
      canAdvance: !!d.effectiveWarehouseId,
      blockHint: 'ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.',
      body: <HeaderStep d={d} warehouses={warehouses} />,
    },
    {
      key: 'lines',
      title: 'اقلام',
      subtitle: 'کالاها، تعداد و قیمت را وارد کنید.',
      canAdvance: d.linesValid,
      blockHint: 'حداقل یک ردیف با کالا و تعداد لازم است؛ و تخفیف نباید از مبلغِ ردیف بیشتر باشد.',
      body: <LinesStep d={d} items={items} />,
    },
    {
      key: 'adjust',
      title: 'تخفیف، مالیات و پرداخت',
      subtitle: 'تخفیفِ کل، رند کردن و در صورتِ نیاز پرداختِ کارتی.',
      body: <AdjustStep d={d} token={token} />,
    },
    {
      key: 'review',
      title: 'بازبینی و ثبت',
      subtitle: 'همه‌چیز را یک‌بار مرور کنید، بعد ثبت را بزنید.',
      //: سقفِ اعتبار این‌جا سنجیده می‌شود نه در مرحله‌ی سربرگ، چون به مبلغِ نهاییِ
      //: فاکتور نیاز دارد و آن تا واردشدنِ اقلام معلوم نیست.
      canAdvance: !d.creditBlock,
      blockHint: 'سقفِ اعتبارِ این مشتری اجازه نمی‌دهد — بالای همین صفحه نوشته چه کار می‌شود کرد.',
      body: <ReviewStep d={d} items={items} warehouses={warehouses} />,
    },
  ]

  return (
    <TaskFlow
      title="ثبت فاکتور فروش"
      steps={steps}
      submitLabel="ثبت فاکتور"
      submitting={d.submitting}
      message={d.message}
      resetKey={resetTick}
      preview={<LivePreview d={d} warehouses={warehouses} />}
      onSubmit={() => {
        void d.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

// ── مرحله ۱: سربرگ و طرف‌حساب ──────────────────────────────────────────────
function HeaderStep({ d, warehouses }: { d: SalesInvoiceDraft; warehouses: WarehouseCache[] }) {
  return (
    <div className="invoice-form">
      <SourceIssueBanner d={d} />
      <label>
        انبار پیشنهادی (اختیاری)
        <SearchSelect
          value={d.effectiveWarehouseId}
          disabled={!!d.sourceIssue}
          onChange={(e) => d.setWarehouseId(e.target.value)}
        >
          <option value="">— خروج انبار بعداً تعیین می‌شود —</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SearchSelect>
      </label>
      <label>
        تاریخ فاکتور
        <JalaliDatePicker value={d.invoiceDate} onChange={d.setInvoiceDate} />
      </label>
      {d.costCenters.length > 0 && (
        <label>
          مرکز هزینه/پروژه (اختیاری)
          <SearchSelect value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
            <option value="">— بدون مرکز —</option>
            {d.costCenters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} — ${c.name}` : c.name}
              </option>
            ))}
          </SearchSelect>
        </label>
      )}
      {d.contacts.length > 0 && (
        <label>
          مشتری (اختیاری)
          <SearchSelect value={d.contactId} onChange={(e) => d.setContactId(e.target.value)}>
            <option value="">— بدون مشتری —</option>
            {d.contacts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </SearchSelect>
          {d.autoTier && (
            <span className="tier-discount-hint">
              {d.autoTier.source === 'tier'
                ? `🎖️ سطحِ ${d.autoTier.name} — تخفیفِ ${d.autoTier.pct.toLocaleString('fa-IR')}٪ اعمال شد`
                : `🏷️ نرخِ تخفیفِ طرف‌حساب — ${d.autoTier.pct.toLocaleString('fa-IR')}٪ اعمال شد`}
            </span>
          )}
        </label>
      )}
      <label>
        نام دوم مشتری (اختیاری)
        <input value={d.customerName2} onChange={(e) => d.setCustomerName2(e.target.value)} maxLength={200} />
      </label>
      <label>
        محل تحویل (اختیاری)
        <input value={d.deliveryLocation} onChange={(e) => d.setDeliveryLocation(e.target.value)} />
      </label>
      <label>
        شرایط تسویه
        <SearchSelect value={d.settlementTerms} onChange={(e) => d.setSettlementTerms(e.target.value as 'cash' | 'credit' | 'mixed')}>
          <option value="credit">نسیه</option>
          <option value="cash">نقدی</option>
          <option value="mixed">نقدی/نسیه</option>
        </SearchSelect>
      </label>
      <label>
        تاریخ سررسید/صورتحساب (اختیاری)
        <JalaliDatePicker value={d.statementDate} onChange={d.setStatementDate} />
      </label>
      <label>
        شرح فاکتور (اختیاری)
        <input value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
      </label>
          {d.salespeople.length > 0 && (
        <FormField label="فروشنده (اختیاری)" tip="مبنای «محاسبه پورسانت»؛ بدونِ آن فاکتور در پورسانت نمی‌آید.">
          {(id) => (
            <SearchSelect id={id} value={d.salespersonId} onChange={(e) => d.setSalespersonId(e.target.value)}>
              <option value="">— بدون فروشنده —</option>
              {d.salespeople.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </SearchSelect>
          )}
        </FormField>
      )}
      {d.saleTypes.length > 0 && (
        <label>
          نوع فروش (اختیاری)
          <SearchSelect value={d.saleTypeId} onChange={(e) => d.setSaleTypeId(e.target.value)}>
          <option value="">— تعیین‌نشده —</option>
          {d.saleTypes.map((t) => (
            <option key={t.id} value={t.id}>
            {t.name}
            </option>
          ))}
          </SearchSelect>
        </label>
      )}
      {d.brokers.length > 0 && (
        <label>
          واسطه (اختیاری)
          <SearchSelect value={d.brokerId} onChange={(e) => d.setBrokerId(e.target.value)}>
            <option value="">— بدون واسطه —</option>
            {d.brokers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </SearchSelect>
          {d.brokerCommission && (
            <span className="field-hint">
              {d.brokerCommission.pct > 0
                ? `کارمزد ${d.brokerCommission.pct.toLocaleString('fa-IR')}٪ — حدود ${d.brokerCommission.amount.toLocaleString('fa-IR')} (مبلغِ قطعی هنگام ثبت قفل می‌شود)`
                : 'نرخِ کارمزدِ این واسطه صفر است — ثبت می‌شود ولی کارمزدی ندارد.'}
            </span>
          )}
        </label>
      )}
      {d.currencies.length > 0 && (
        <div className="field-row">
          <label>
            ارز فاکتور
            <SearchSelect value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
              <option value="">ریال (پایه)</option>
              {d.currencies.map((c) => (
                <option key={c.id} value={c.code}>
                  {c.code} — {c.name}
                </option>
              ))}
            </SearchSelect>
          </label>
          {d.currencyCode && (
            <label>
              نرخ برابری (۱ {d.currencyCode} = ؟ ریال)
              <NumberInput allowDecimal value={d.exchangeRate} onChange={d.setExchangeRate} />
            </label>
          )}
        </div>
      )}
      {d.blacklisted && <BlacklistBanner name={d.contacts.find((c) => c.id === d.contactId)?.name} />}
      {d.creditBlock && (
        <section className="fy-note fy-note--err">
          <AlertTriangle size={16} />
          <div>
            <strong>{d.creditBlock.name}</strong> از سقفِ اعتبارش رد می‌شود: این فاکتور
            مانده را به {Math.round(d.creditBlock.projected).toLocaleString('fa-IR')} می‌رساند و
            سقفش {Math.round(d.creditBlock.limit).toLocaleString('fa-IR')} ریال است.
            <span className="credit-banner-alert">
              در فرمِ طرف حساب «با عبور از سقف» روی «جلوگیری کن» است. یا دریافتی ثبت کنید،
              یا سقف را بالا ببرید، یا آن تنظیم را به «هشدار بده» تغییر دهید.
            </span>
          </div>
        </section>
      )}
      {d.credit && Number(d.credit.credit_limit) > 0 && (
        <CreditBanner credit={d.credit} invoiceTotal={d.baseGrandTotal} />
      )}
    </div>
  )
}

// ── مرحله ۲: اقلام ────────────────────────────────────────────────────────
function LinesStep({ d, items }: { d: SalesInvoiceDraft; items: ItemCache[] }) {
  return (
    <>
      <div className="table-scroll">
        <table className="invoice-lines cards-on-mobile">
          <thead>
            <tr>
              <th>کالا</th>
              <th>تعداد</th>
              <th>موجودی انبار</th>
              <th>قیمت واحد</th>
              <th>تخفیف</th>
              <th>اضافات</th>
              <th>عوارض</th>
              <th>مبلغ</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {d.lines.map((line, i) => {
              const avail = d.availableStock(line.itemId)
              const service = d.isService(line.itemId)
              const over = avail != null && Number(line.qty) > avail
              const unit = items.find((it) => it.id === line.itemId)?.unit
              return (
                <tr key={i}>
                  <td data-label="کالا">
                    <ItemPicker items={items} value={line.itemId} onChange={(id) => d.chooseLineItem(i, id)} />
                  </td>
                  <td data-label="تعداد">
                    <div className="qty-with-unit">
                      <NumberInput allowDecimal value={line.qty} onChange={(v) => d.updateLine(i, { qty: v })} />
                      {unit ? <span className="unit-suffix">{unit}</span> : null}
                    </div>
                  </td>
                  <td data-label="موجودی انبار">
                    {!line.itemId ? (
                      '—'
                    ) : service ? (
                      <span className="unit-suffix">خدمات (بدون موجودی)</span>
                    ) : (
                      <div className="stock-cell">
                        <span className={over ? 'stock-over' : 'stock-ok'}>
                          {avail != null ? avail.toLocaleString('fa-IR') : '—'} {unit}
                        </span>
                        {over && <div className="stock-warn">بیش از موجودی</div>}
                      </div>
                    )}
                  </td>
                  <td data-label="قیمت واحد">
                    <NumberInput
                      value={line.unitPrice}
                      onChange={(v) => d.updateLine(i, { unitPrice: v })}
                      title={(() => {
                        const u = items.find((it) => it.id === line.itemId)?.unit
                        return u ? `قیمت هر ${u}` : 'قیمت واحد'
                      })()}
                    />
                    <PriceRuleHint rule={d.priceInfo[line.itemId]} entered={line.unitPrice} />
                  </td>
                  <td data-label="تخفیف">
                    <NumberInput value={line.discount} onChange={(v) => d.updateLine(i, { discount: v })} placeholder="۰" />
                  </td>
                  <td data-label="اضافات">
                    <NumberInput value={line.addition} onChange={(v) => d.updateLine(i, { addition: v })} placeholder="۰" />
                  </td>
                  <td data-label="عوارض">
                    <NumberInput value={line.dutyAmount} onChange={(v) => d.updateLine(i, { dutyAmount: v })} placeholder="۰" />
                  </td>
                  <td data-label="مبلغ">
                    <span className={`line-amount${line.itemId ? '' : ' muted'}`}>
                      {line.itemId
                        ? Math.max(
                            (Number(line.qty) || 0) * (Number(line.unitPrice) || 0) - (Number(line.discount) || 0),
                            0,
                          ).toLocaleString('fa-IR')
                        : '—'}
                    </span>
                  </td>
                  <td className="card-actions">
                    <button
                      type="button"
                      className="icon-btn-danger"
                      onClick={() => d.removeLine(i)}
                      disabled={d.lines.length === 1}
                      aria-label="حذف ردیف"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div>
        <button type="button" onClick={d.addLine}>
          <Plus size={14} /> افزودن ردیف
        </button>
      </div>
    </>
  )
}

// ── مرحله ۳: تخفیف، مالیات و پرداخت ───────────────────────────────────────
function AdjustStep({ d, token }: { d: SalesInvoiceDraft; token: string }) {
  return (
    <div className="invoice-form">
      <label>
        نرخ مالیات بر ارزش افزوده (٪)
        <NumberInput allowDecimal value={d.taxRate} onChange={d.setTaxRate} />
      </label>
      <div className="invoice-adjustments">
        <label className="adj-field">
          تخفیف کل فاکتور
          <div className="qty-with-unit">
            <NumberInput value={d.invoiceDiscount} onChange={d.setInvoiceDiscount} placeholder="۰" />
            <div className="seg-toggle">
              <button type="button" className={d.invoiceDiscountMode === 'amount' ? 'active' : ''} onClick={() => d.setInvoiceDiscountMode('amount')}>
                مبلغ
              </button>
              <button type="button" className={d.invoiceDiscountMode === 'percent' ? 'active' : ''} onClick={() => d.setInvoiceDiscountMode('percent')}>
                ٪
              </button>
            </div>
          </div>
          {d.invoiceDiscountMode === 'percent' && d.invoiceDiscountAmount > 0 && (
            <span className="hint">معادل {d.invoiceDiscountAmount.toLocaleString('fa-IR')}</span>
          )}
        </label>
        {!d.currencyCode && (
          <label className="adj-field">
            رند کردن مبلغ نهایی (به پایین)
            <div className="seg-toggle">
              {[0, 1000, 5000, 10000].map((s) => (
                <button key={s} type="button" className={d.roundStep === s ? 'active' : ''} onClick={() => d.setRoundStep(s)}>
                  {s === 0 ? 'بدون' : s.toLocaleString('fa-IR')}
                </button>
              ))}
            </div>
          </label>
        )}
      </div>
      {d.contactId && d.baseGrandTotal > 0 && (
        <CardPaymentButton
          token={token}
          amount={d.baseGrandTotal}
          contactId={d.contactId}
          description="پرداختِ کارتیِ فاکتورِ فروش"
          onPaid={() => d.setMessage('پرداختِ کارتی روی حسابِ این مشتری ثبت شد. برای ثبتِ خودِ فاکتور، مرحله‌ی بعد «ثبت فاکتور» را بزنید.')}
        />
      )}
    </div>
  )
}

// ── مرحله ۴: بازبینی و ثبت ────────────────────────────────────────────────
function ReviewStep({ d, items, warehouses }: { d: SalesInvoiceDraft; items: ItemCache[]; warehouses: WarehouseCache[] }) {
  const customer = d.contacts.find((c) => c.id === d.contactId)
  const warehouse = warehouses.find((w) => w.id === d.effectiveWarehouseId)
  const validLines = d.lines.filter((l) => l.itemId && Number(l.qty) > 0)
  return (
    <div className="review-step">
      <p className="form-subhead">طرف‌حساب</p>
      <div className="review-facts">
        <div className="live-preview-row">
          <span>مشتری</span>
          <strong>{customer?.name ?? 'بدون مشتری'}</strong>
        </div>
        <div className="live-preview-row">
          <span>انبار</span>
          <strong>{warehouse?.name ?? '—'}</strong>
        </div>
        <div className="live-preview-row">
          <span>تاریخ</span>
          <strong>{d.invoiceDate}</strong>
        </div>
        {d.currencyCode && (
          <div className="live-preview-row">
            <span>ارز</span>
            <strong>{d.currencyCode}</strong>
          </div>
        )}
      </div>
      <p className="form-subhead">اقلام</p>
      <div className="table-scroll">
        <table className="cards-on-mobile">
          <thead>
            <tr>
              <th>کالا</th>
              <th>تعداد</th>
              <th>قیمت واحد</th>
              <th>تخفیف</th>
              <th>مبلغ</th>
            </tr>
          </thead>
          <tbody>
            {validLines.map((line, i) => {
              const it = items.find((x) => x.id === line.itemId)
              const amount = Math.max((Number(line.qty) || 0) * (Number(line.unitPrice) || 0) - (Number(line.discount) || 0), 0)
              return (
                <tr key={i}>
                  <td data-label="کالا">{it?.name ?? '—'}</td>
                  <td data-label="تعداد">{Number(line.qty).toLocaleString('fa-IR')} {it?.unit ?? ''}</td>
                  <td data-label="قیمت واحد">{Number(line.unitPrice || 0).toLocaleString('fa-IR')}</td>
                  <td data-label="تخفیف">{Number(line.discount || 0).toLocaleString('fa-IR')}</td>
                  <td data-label="مبلغ">{amount.toLocaleString('fa-IR')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── پنلِ پیش‌نمایشِ زنده (کنارِ همه‌ی مراحل) ────────────────────────────────
function LivePreview({ d, warehouses }: { d: SalesInvoiceDraft; warehouses: WarehouseCache[] }) {
  const customer = d.contacts.find((c) => c.id === d.contactId)
  const warehouse = warehouses.find((w) => w.id === d.effectiveWarehouseId)
  const lineCount = d.lines.filter((l) => l.itemId && Number(l.qty) > 0).length
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ فاکتور</p>
      <div className="live-preview-row">
        <span>مشتری</span>
        <strong>{customer?.name ?? 'بدون مشتری'}</strong>
      </div>
      <div className="live-preview-row">
        <span>انبار</span>
        <strong>{warehouse?.name ?? '—'}</strong>
      </div>
      <div className="live-preview-row">
        <span>تاریخ</span>
        <strong>{d.invoiceDate}</strong>
      </div>
      <div className="live-preview-row">
        <span>تعداد اقلام</span>
        <strong>{lineCount.toLocaleString('fa-IR')}</strong>
      </div>
      <div className="live-preview-divider" />
      <div className="live-preview-row">
        <span>جمع خالص</span>
        <strong>{fa(d.total)}</strong>
      </div>
      {d.discountTotal > 0 && (
        <div className="live-preview-row">
          <span>تخفیف سطری</span>
          <strong>{fa(d.discountTotal)}</strong>
        </div>
      )}
      {d.invoiceDiscountAmount > 0 && (
        <div className="live-preview-row">
          <span>تخفیف کل</span>
          <strong>{fa(d.invoiceDiscountAmount)}</strong>
        </div>
      )}
      <div className="live-preview-row">
        <span>مالیات ({d.taxRateNum.toLocaleString('fa-IR')}٪)</span>
        <strong>{fa(d.taxAmount)}</strong>
      </div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total">
        <span>قابل پرداخت</span>
        <strong>
          {fa(d.grandTotal)}
          {d.currencyCode ? ` ${d.currencyCode}` : ''}
        </strong>
      </div>
      {d.currencyCode && (
        <div className="live-preview-row">
          <span>معادل ریالی</span>
          <strong>{fa(d.baseGrandTotal)}</strong>
        </div>
      )}
    </div>
  )
}
