import { ShoppingCart, Plus, Trash2, Save, AlertTriangle } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import type { CreditStatus, SalesInvoiceRecord } from '../api'
import { CardPaymentButton } from './CardPaymentDialog'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ItemPicker } from './ItemPicker'
import { PriceRuleHint } from './PriceRuleHint'
import { useSalesInvoiceDraft } from '../lib/salesInvoiceDraft'
import { BlacklistBanner } from './BlacklistBanner'

/**
 * فرمِ کلاسیکِ «ثبتِ فاکتورِ فروش» (پوسته‌های تیره/روشن) — همه‌ی فیلدها در یک صفحه.
 * منطق در هوکِ مشترکِ [useSalesInvoiceDraft] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند.
 */
export function SalesInvoiceForm({
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
  /** رونوشتِ فاکتور: فرم را با اقلامِ یک فاکتورِ موجود پیش‌پر می‌کند (به‌عنوان پیش‌نویسِ تازه). */
  prefill?: SalesInvoiceRecord | null
  onPrefillConsumed?: () => void
}) {
  const d = useSalesInvoiceDraft({ token, warehouses, items, onQueued, prefill, onPrefillConsumed })

  return (
    <SectionCard icon={ShoppingCart} title="ثبت فاکتور فروش">
      {items.length === 0 ? (
        <p className="hint">قبل از ثبت فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا کالاها در دسترس باشند.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void d.submit()
          }}
        >
          <label>
            انبار پیشنهادی (اختیاری)
            <select value={d.effectiveWarehouseId} onChange={(e) => d.setWarehouseId(e.target.value)}>
              <option value="">— خروج انبار بعداً تعیین می‌شود —</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ فاکتور
            <JalaliDatePicker value={d.invoiceDate} onChange={d.setInvoiceDate} />
          </label>
          <label>
            نرخ مالیات بر ارزش افزوده (٪)
            <NumberInput allowDecimal value={d.taxRate} onChange={d.setTaxRate} />
          </label>
          {d.costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <select value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code ? `${c.code} — ${c.name}` : c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {d.contacts.length > 0 && (
            <label>
              مشتری (اختیاری)
              <select value={d.contactId} onChange={(e) => d.setContactId(e.target.value)}>
                <option value="">— بدون مشتری —</option>
                {d.contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              {d.autoTier && (
                <span className="tier-discount-hint">
                  🎖️ سطحِ {d.autoTier.name} — تخفیفِ {d.autoTier.pct.toLocaleString('fa-IR')}٪ اعمال شد
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
            <select value={d.settlementTerms} onChange={(e) => d.setSettlementTerms(e.target.value as 'cash' | 'credit' | 'mixed')}>
              <option value="credit">نسیه</option>
              <option value="cash">نقدی</option>
              <option value="mixed">نقدی/نسیه</option>
            </select>
            <span className="field-hint">نقدی بودن، وصول را خودکار نمی‌سازد؛ رسید دریافت جدا ثبت می‌شود.</span>
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
            <label>
              فروشنده (اختیاری)
              <select value={d.salespersonId} onChange={(e) => d.setSalespersonId(e.target.value)}>
                <option value="">— بدون فروشنده —</option>
                {d.salespeople.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <span className="field-hint">مبنای «محاسبه پورسانت»؛ بدونِ آن فاکتور در پورسانت نمی‌آید.</span>
            </label>
          )}
          {d.saleTypes.length > 0 && (
            <label>
              نوع فروش (اختیاری)
              <select value={d.saleTypeId} onChange={(e) => d.setSaleTypeId(e.target.value)}>
                <option value="">— تعیین‌نشده —</option>
                {d.saleTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {d.brokers.length > 0 && (
            <label>
              واسطه (اختیاری)
              <select value={d.brokerId} onChange={(e) => d.setBrokerId(e.target.value)}>
                <option value="">— بدون واسطه —</option>
                {d.brokers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
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
                <select value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
                  <option value="">ریال (پایه)</option>
                  {d.currencies.map((c) => (
                    <option key={c.id} value={c.code}>
                      {c.code} — {c.name}
                    </option>
                  ))}
                </select>
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

          {/* ── تخفیفِ کلِ فاکتور و گِرد کردنِ مبلغِ نهایی ── */}
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

          <div className="invoice-form-footer">
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <div className="invoice-totals">
              {d.discountTotal > 0 && <span>تخفیف سطری: {d.discountTotal.toLocaleString('fa-IR')}</span>}
              {d.invoiceDiscountAmount > 0 && <span>تخفیف کل: {d.invoiceDiscountAmount.toLocaleString('fa-IR')}</span>}
              <span>جمع خالص: {d.total.toLocaleString('fa-IR')}</span>
              {d.additionsTotal > 0 && <span>اضافات: {d.additionsTotal.toLocaleString('fa-IR')}</span>}
              {d.dutiesTotal > 0 && <span>عوارض: {d.dutiesTotal.toLocaleString('fa-IR')}</span>}
              <span>مالیات ({d.taxRateNum.toLocaleString('fa-IR')}٪): {d.taxAmount.toLocaleString('fa-IR')}</span>
              <span className="invoice-total">
                قابل پرداخت: {d.grandTotal.toLocaleString('fa-IR')}
                {d.currencyCode ? ` ${d.currencyCode}` : ''}
              </span>
              {d.currencyCode && <span className="hint">معادل ریالی: {d.baseGrandTotal.toLocaleString('fa-IR')}</span>}
            </div>
            {d.contactId && d.baseGrandTotal > 0 && (
              <CardPaymentButton
                token={token}
                amount={d.baseGrandTotal}
                contactId={d.contactId}
                description="پرداختِ کارتیِ فاکتورِ فروش"
                onPaid={() => d.setMessage('پرداختِ کارتی روی حسابِ این مشتری ثبت شد. برای ثبتِ خودِ فاکتور، «ثبت فاکتور» را بزنید.')}
              />
            )}
            <button type="submit" className="btn-primary" disabled={d.submitting || Boolean(d.creditBlock)}>
              <Save size={14} /> ثبت فاکتور
            </button>
          </div>

          {d.message && <div className="hint">{d.message}</div>}
        </form>
      )}
    </SectionCard>
  )
}

// بنر اعتبار — مانده و سقفِ مشتری را نشان می‌دهد و اگر این فاکتور مانده را از سقف
// عبور دهد، هشدار می‌دهد. عمداً بلاک‌کننده نیست: تصمیمِ فروش با کاربر است و فاکتورهای
// آفلاین هم نباید سمت سرور رد شوند — این فقط یک هشدارِ آگاه‌کننده است.
export function CreditBanner({ credit, invoiceTotal }: { credit: CreditStatus; invoiceTotal: number }) {
  const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
  const limit = Number(credit.credit_limit)
  const outstanding = Number(credit.outstanding)
  const available = limit - outstanding
  const projected = outstanding + invoiceTotal
  const willExceed = projected > limit

  return (
    <div className={`credit-banner ${willExceed ? 'credit-banner--warn' : 'credit-banner--ok'}`}>
      {willExceed && <AlertTriangle size={15} />}
      <span>
        مانده فعلی: <strong>{fa(outstanding)}</strong> از سقف <strong>{fa(limit)}</strong> ریال
        {' — '}
        قابل استفاده: <strong>{fa(available)}</strong>
      </span>
      {willExceed && (
        <span className="credit-banner-alert">
          این فاکتور مانده را به {fa(projected)} می‌رساند و از سقف اعتبار عبور می‌کند.
        </span>
      )}
    </div>
  )
}
