---
name: cubita-excel-theme
description: روشِ بازسازیِ صفحه‌ها با «تمِ اکسلیِ سند حسابداری» — گریدِ xl-grid، سربرگ و نوارِ پایینِ هم‌خط با ستون‌ها، DocFooter/BalanceFooter/SheetFooter، صفحه‌کلیدِ اکسلی، ذخیره‌ی یک‌جا و پیش‌نویس. هر بار که صفحه‌ای به این تم برده می‌شود یا کاربر می‌گوید «صفحه‌ی بعدی را با همین تم»، اول این را بخوان (بعد از cubita-page). Use when rebuilding or restyling any Cubita desktop/web page into the Excel-like journal theme, or when continuing the page-by-page theme rebuild.
---

# تمِ اکسلیِ سند حسابداری — بازسازیِ صفحه به صفحه

آرش صفحه‌ی «سند حسابداری» را پسندید و خواست **صفحه‌ها تک‌به‌تک** با همین تم بازسازی شوند. هدف
یکدستی است: هر صفحه‌ای که با داده‌ی ردیفی کار می‌کند، از دیدِ حسابدار باید مثلِ یک برگه‌ی اکسل
رفتار کند. پس گرید با خطوطِ ظریف و سرستونِ خاکستری، و سربرگ و نوارِ پایین **ستون‌به‌ستون** زیر و
بالای همان ستون‌ها. صفحه‌کلید هم همان رفتارِ همیشگی را دارد.

پیش از این، [cubita-page](../cubita-page/SKILL.md) را بخوان. پوسته، قاعده‌ی عملیات و فهرست،
موبایل و ممیز همه از آن‌جا می‌آیند. این سند فقط لایه‌ی **تم** را می‌گوید.

## وضعیت

| صفحه | PR | الگو (بخشِ ۱) | فایلِ مرجع |
|---|---|---|---|
| سند حسابداری | #205 | الف: سند | [JournalEntryForm.tsx](../../../desktop/src/components/JournalEntryForm.tsx) |
| مانده اول دوره | #206 | الف: سند، به‌اضافه‌ی برگه‌ی کالا | [OpeningBalancePage.tsx](../../../desktop/src/pages/accounting/OpeningBalancePage.tsx) |
| تفصیلی سایر | #207 | ب: برگه‌ی ویرایشِ درجا | [AnalyticsPage.tsx](../../../desktop/src/pages/accounting/AnalyticsPage.tsx) |
| صدور سند تسعیر ارز | #208 | ج: پیش‌نمایشِ سندِ خودکار | [FxRevaluationPage.tsx](../../../desktop/src/pages/accounting/FxRevaluationPage.tsx) |
| ارزها و نرخ برابری | #209 | ب: دو برگه در یک فرم | [CurrenciesPanel.tsx](../../../desktop/src/components/CurrenciesPanel.tsx) |
| اسناد حسابداری (فهرست) | پیش از #205 | د: دفتر | `EntryTable` در [JournalPages.tsx](../../../desktop/src/pages/accounting/JournalPages.tsx) |
| اسناد تکرارشونده | #212 | الف برای فرمِ قالب + د برای فهرستِ قالب‌ها | [RecurringPage.tsx](../../../desktop/src/pages/accounting/RecurringPage.tsx) |
| بودجه‌بندی | #213 | ب: ماتریسِ حساب × ماه (ستون‌های ثابت، لغزشِ افقی) | [BudgetPage.tsx](../../../desktop/src/pages/accounting/BudgetPage.tsx) |
| انتقال حساب به سرفصل دیگر | (این PR) | ب: یک ستونِ ویرایشی روی ردیف‌های ثبت‌شده، بی ردیفِ تازه؛ ذخیره‌ی اتمیِ یک‌درخواسته | [ReclassifyPage.tsx](../../../desktop/src/pages/accounting/ReclassifyPage.tsx) |

**بعدی:** وقتی صفحه‌ای تمام شد، ردیفش را این‌جا اضافه کن. صفحه‌ی بعدی را آرش انتخاب می‌کند.
منوهای حسابداری پیش از این در #211 بازچینی شدند (شش دسته، تکراری‌ها ادغام) — صفحه‌ای را که ادغام شده
دوباره نساز؛ فهرستِ فعلی در `NAV_GROUPS` است و کلیدهای رفته در `LEGACY_PAGES`.

---

## ۱. اول الگو را انتخاب کن

هر صفحه یکی از این چهار است. الگو تعیین می‌کند کدام نوار و کدام منطقِ ذخیره.

| الگو | کی | نوارِ پایین | مرجع |
|---|---|---|---|
| **الف: سند** | ردیف‌های بدهکار/بستانکار که باید تراز شوند | `BalanceFooter` + `balanceState()` | سند حسابداری، مانده اول دوره |
| **ب: برگه‌ی ویرایشِ درجا** | داده‌ی پایه (تعریف‌ها) که ردیف‌به‌ردیف ساخته و ویرایش می‌شود | `SheetFooter` (`clean`/`dirty`/`err`) | تفصیلی سایر، ارزها |
| **ج: پیش‌نمایشِ سندِ خودکار** | سرور حساب می‌کند و کاربر فقط بازه و گزینه می‌دهد و «صدور» می‌زند | `DocFooter` با `statusEnd` | تسعیر ارز |
| **د: دفتر/فهرست** | مرورِ رکوردهای ثبت‌شده با فیلترِ سرستون و انتخاب | بی‌نوار؛ `SelectionBar` جمعِ انتخاب را می‌گوید | فهرستِ اسناد |

**مرزِ «ب» و «فهرست»:** اگر صفحه‌ی داده‌ی پایه با این تم برگه‌ی کاملِ ویرایشِ درجا شد، فهرستِ جدایش
«دو نمای یک داده» می‌شود. قاعده‌ی ۷ِ CLAUDE.md می‌گوید یکی‌شان کن. کلیدِ فهرست را در `OPS_LIST_MAP`
به `'view'` ببر (مثلِ «حساب بانکی») و منوی فهرست را بردار.

---

## ۲. قطعه‌های مشترک — از نو نساز

| قطعه | فایل | چه می‌کند |
|---|---|---|
| `useColumnWidths(key, LAYOUT)` | [lib/useColumnWidths.ts](../../../desktop/src/lib/useColumnWidths.ts) | عرضِ ستون‌ها در حالتِ «جا در قاب»: جدول هم‌عرضِ قاب، کشیدنِ لبه فقط دو ستونِ هم‌سایه را عوض می‌کند. `cw.col(id)` برای `<col>`، `cw.frame` ref روی `<table>`. `fitShares` کفِ ستونِ کشسان را (۱۶۰px) در زمانِ نمایش نگه می‌دارد. |
| `useAlignToGrid(rootRef, followers, {table, slots})` | [lib/alignToGrid.ts](../../../desktop/src/lib/alignToGrid.ts) | عرضِ ستون‌های گرید را می‌سنجد و `--jg-cols` (پنج خانه) را روی سربرگ (`.jh-bar`) و نوار (`.jf-foot--cols`) می‌نویسد. |
| `DocFooter` | [components/DocFooter.tsx](../../../desktop/src/components/DocFooter.tsx) | پایه‌ی نوارِ چسبنده: دکمه، خانه‌ی وضعیت، دو خانه‌ی عدد. `tone`: `ok`/`err`/`warn`/`auto`/`empty`. `columns` هم‌خطی را روشن می‌کند؛ `statusEnd` وضعیت را به خانه‌ی پنجم می‌برد. |
| `BalanceFooter` | [components/BalanceFooter.tsx](../../../desktop/src/components/BalanceFooter.tsx) | `DocFooter` برای سند: جمعِ بدهکار، جمعِ بستانکار و توازن. `autoNote` برای اختلافی که خودکار بسته می‌شود («به سرمایه»). |
| `balanceState()` | [lib/balanceState.ts](../../../desktop/src/lib/balanceState.ts) | `empty`/`ok`/`err`/`auto` از جمع‌ها. |
| `SheetFooter` | [components/SheetFooter.tsx](../../../desktop/src/components/SheetFooter.tsx) | `DocFooter` برای برگه: «ذخیره تغییرات»، شمارِ تازه و ویرایش‌شده؛ سبز/زرد/قرمز. |
| `useSheetNav<C>()` | [lib/useSheetNav.ts](../../../desktop/src/lib/useSheetNav.ts) | صفحه‌کلیدِ اکسلی برای خانه‌های `data-cell="ردیف-ستون"`: Enter/Tab/پیکان‌ها/F2/Ctrl+Enter/Ctrl+Delete. منطقِ خالصش در `journalGridNav.ts` است. |
| `ColResizer`، `SelectionBar` | [components/XlGrid.tsx](../../../desktop/src/components/XlGrid.tsx) | دستگیره‌ی کشیدنِ لبه‌ی ستون؛ نوارِ «n ردیف انتخاب شد» با جمع و کنش‌های دسته‌ای. |
| `FitText` | [components/FitText.tsx](../../../desktop/src/components/FitText.tsx) | عددی که در خانه جا نشود کوچک می‌شود، نه خانه بزرگ. |
| `AccountCombo` (`emptyText`)، `SearchSelect`، `JalaliDatePicker` | components/ | انتخاب‌گرهای درونِ خانه. در گرید بی‌قاب می‌شوند (قاعده‌ی `xl-grid` در App.css). |
| `tenantKey()` | [lib/tenantScope.ts](../../../desktop/src/lib/tenantScope.ts) | کلیدِ `sessionStorage`ِ پیش‌نویس، جدا برای هر کسب‌وکار. |

اگر قطعه‌ای کم بود، **همین‌ها را گسترش بده** (پارامترِ تازه با پیش‌فرضِ رفتارِ فعلی). نسخه‌ی دوم نساز.
`BalanceFooter` و `SheetFooter` هر دو رَپرِ `DocFooter`اند. نوارِ تازه هم باید رَپرِ همان باشد.

---

## ۳. اسکلتِ برگه (الگوی ب)

```tsx
const LAYOUT = { fixed: ['num', 'actions'], auto: 'name' } as const
//: پنج خانه‌ی نوار روی ستون‌های این برگه: [دکمه] [وضعیت] [عدد ۱] [عدد ۲] [باقی]
const SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('num') + w('code') + w('name'), w('group'), w('description'), w('lines') + w('active'), w('actions')]
}

const formRef = useRef<HTMLFormElement>(null)
const cw = useColumnWidths('cubita.grid.<page>.shares', LAYOUT)
useAlignToGrid(formRef, '.jf-foot--cols', { table: '.xx-sheet', slots: SLOTS })
const nav = useSheetNav<Col>({ gridRef, cols: COLS, rowCount: rows.length, onAppendRow, onDeleteRow })

<OpsPage canvas icon={…} title="…" description="…" head={<div className="cc-head"><div className="cc-summary"><Metric …/></div></div>}>
  <form ref={formRef} noValidate onSubmit={…save} onKeyDown={/* Ctrl+S ذخیره، Ctrl+F جست‌وجوی برگه */}>
    <SectionCard icon={…} title="…" tip="…" badge={<CountBadge accent>…</CountBadge>}
                 actions={<div className="jg-head-actions"><div className="jg-find">…</div></div>}>
      <div className="jg">
        <div className="table-scroll ef-table-wrap jg-wrap" ref={gridRef} onKeyDown={nav.onKeyDown}>
          <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain xx-sheet">
            <colgroup><col className="jg-c-num" style={cw.col('num')} />…</colgroup>
            <thead><tr><th className="ef-col-min xl-rowhead" data-col="num">…</th>… <th data-col="…">…<ColResizer …/></th></tr></thead>
            <tbody>{rows.map((r, i) => <SheetRow key={r.key} … />)}</tbody>
          </table>
        </div>
        <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>…</SelectionBar>
      </div>
      {errors.length > 0 && <ul className="xl-errbar" role="alert">…</ul>}
    </SectionCard>
    <SheetFooter columns state={state} … />
  </form>
</OpsPage>
```

**چند برگه در یک فرم** (ارزها): هر برگه جدول و `SLOTS`ِ خودش را دارد. نوار فقط با **یکی**
(برگه‌ی اصلی) هم‌خط می‌شود. `table` در `useAlignToGrid` همان را نشان بدهد.

---

## ۴. ستون‌ها

- `<th data-col="id">` روی **ردیفِ اولِ** `thead`. هم `useColumnWidths` و هم `useAlignToGrid` از
  همین می‌خوانند.
- `LAYOUT.fixed` برای شماره‌ی ردیف و آیکون‌هاست (عرضِ پیکسلی از CSS) و `LAYOUT.auto` یک ستونِ
  کشسان است (معمولاً «حساب» یا «نام»). بقیه درصدی‌اند.
- عرضِ پیش‌فرض را کلاسِ `<col className="jg-c-…">` در App.css می‌دهد، کنارِ بلوکِ
  `.jg-table col.jg-c-*`. پیش از ساختنِ کلاسِ تازه، کلاس‌های موجود را ببین (`jg-c-code`، `jg-c-group`،
  `jg-c-note`، `jg-c-date`، `jg-c-chg`، `jg-c-sym`، `jg-c-last` و …).
- کلیدِ ذخیره: `cubita.grid.<page>.shares`. **اگر شناسه‌ی ستون‌ها عوض شد، کلید را هم عوض کن.**
  سهم‌های قدیمی روی ستون‌های تازه همان باگِ «ستونِ حساب در برنامه ناپدید شد» را می‌سازند.

## ۵. سربرگ و نوارِ هم‌خط

- هر دو گریدِ پنج‌خانه‌ای‌اند و مرزها همان مرزِ ستون‌های گرید است:
  ۱. دکمه/عنوان، ۲. وضعیت/شرح، ۳. عددِ اول، ۴. عددِ دوم، ۵. باقی.
  `SlotMap` می‌گوید کدام ستون‌ها در کدام خانه جمع شوند.
- دکمه‌ی اصلی در خانه‌ی ۱ **وسطِ خانه** است (`justify-self: center`).
- سربرگِ فیلدها (`.jh-bar` با `.jh-field`، `jh-field--grow`، `jh-field--rest`) فقط در الگوی «الف»
  است. نمونه: مانده اول دوره.
- وقتی گرید افقی می‌لغزد، هم‌خطی ممکن نیست. متغیر برداشته می‌شود و `--jg-cols-default`ِ CSS جایش را
  می‌گیرد. این رفتارِ درست است، باگ نیست.
- رنگِ خطِ دومِ وضعیت با `tone` می‌آید (`.jb-sum--ok .jb-sub` سبز). متنِ لاتین در خطِ دوم
  (کدِ ارز) را در `sub.side` بگذار تا `unicode-bidi: isolate` بگیرد.

## ۶. کلاس‌های خانه و ردیف

| کلاس | معنا |
|---|---|
| `td.xl-ro` | عددِ محاسبه‌شده، فقط‌خواندنی، خاکستری. `pos-in` سبز و `pos-out` قرمز (مثلِ ستونِ «تغییر»). |
| `td.xl-txt` | متنِ ذخیره‌شده‌ای که سرور ویرایشش را ندارد. مثلاً ارزِ ثبت‌شده. |
| `td.is-changed` | خانه‌ی عوض‌شده‌ی ذخیره‌نشده (ته‌رنگ). |
| `tr.xl-row--new` / `--dirty` / `--error` | ردیفِ تازه / ویرایش‌شده / ردشده از سرور. |
| `.xl-rowhead`، `.xl-rowhead-btn`، `.xl-rowhead-num` | شماره‌ی ردیف. کلیک، Ctrl و Shift روی آن ردیف را انتخاب می‌کنند. |
| `.xl-toggle` (`is-on`) | وضعیتِ فعال/غیرفعال درونِ خانه. |
| `.xl-errbar` | فهرستِ دلیلِ ردیف‌های ردشده، زیرِ برگه. |
| `.xl-ro-note` | یادداشتِ کوچکِ خاکستری درونِ خانه (مثلاً تاریخِ «نرخِ آخر»). |

## ۷. صفحه‌کلید

- رفتارِ همه‌ی برگه‌ها یکی است، از `useSheetNav`: Enter و Shift+Enter خانه‌ی بعد و قبل در
  `enterPath`، Tab، پیکان‌ها با قاعده‌ی لبه‌ی مکان‌نما، F2، Ctrl+Enter ردیفِ تازه، Ctrl+Delete حذفِ ردیف.
- روی انتخاب‌گرِ بسته‌ی خالی، Enter بازش می‌کند و رد نمی‌شود.
- `onAppendRow` باید اندیسِ ردیفِ تازه را برگرداند.
- Ctrl+S (ذخیره) و Ctrl+F (جست‌وجوی برگه، به‌جای یافتنِ مرورگر) روی `onKeyDown`ِ فرم‌اند.

## ۸. ذخیره و پیش‌نویس (الگوی ب)

- **اول ببین سرور چه اجازه می‌دهد** و برگه را همان‌طور بساز. ارز فقط ساخته و حذف می‌شود، پس ارزِ
  ثبت‌شده `xl-txt` است. نرخ «ثبت یا جایگزین» است، پس فقط عددش ویرایش می‌شود. قابلیتی که بک‌اند ندارد را
  در رابط وانمود نکن.
- منطقِ خالص به `lib/<page>Sheet.ts` می‌رود، با تستِ واحدِ جدا. نمونه‌ها `analyticsSheet.ts` و
  `currencySheet.ts` هستند. این فایل‌ها `withTrailingBlank`، `problemOf`، `patchOf`، `pendingCount` و
  `parseDraft` دارند.
- **همیشه دقیقاً یک ردیفِ خالیِ ته** برای ردیفِ تازه هست. خالی‌های وسط دست نمی‌خورند.
- ذخیره یک‌جا و **پشتِ‌سرِ‌هم** است، نه موازی. ردیفی که سرور رد کرد ورودی‌اش را نگه می‌دارد، قرمز
  می‌شود و دلیلش در `xl-errbar` می‌آید. بقیه ذخیره می‌شوند.
- خطای پیش از ارسال (کدِ تکراری، فیلدِ لازم) همان‌جا نشان داده می‌شود و درخواستی نمی‌رود.
- پیش‌نویس در `sessionStorage` زیرِ `tenantKey('cubita.<page>.draft')` می‌ماند و با خالی‌شدن پاک
  می‌شود. پیش‌نویسِ خراب یعنی «هیچ».
- پنلی که درونِ صفحه‌ی دیگری هم می‌نشیند، `onSaved` می‌گیرد تا آن صفحه دوباره حساب کند. نمونه:
  نرخ‌ها زیرِ تسعیر.

## ۹. موبایل (≤۷۶۰px) — بخشی از «تمام‌شده»

- **برگه‌ی ویرایشی** (`jg-table`، `table-plain`) کارت نمی‌شود. کمینه‌ی عرضش حفظ می‌شود و درونِ
  `.jg-wrap` خودش می‌لغزد. صفحه نباید سرریز کند. نوار به چیدمانِ موبایلش می‌رود و ستونی نیست.
- **گریدِ فقط‌خواندنی** (الگوی ج و د) زیرِ ۷۶۰ کارت می‌شود: `cards-on-mobile` و `data-label` روی هر
  `td`. ممیز (R3) سلول‌های درونِ کامپوننتِ ردیفِ جدا را هم می‌گیرد، پس `card-title`/`card-actions` را
  آن‌جا هم بگذار.

## ۱۰. تله‌هایی که واقعاً زمین زدند

- **نوارِ چسبنده z=20 است** (`.jf-dock`، `.ef-actions`). هر پاپ‌آور (تقویم، انتخاب‌گر) باید دستِ‌کم
  z=30 باشد، وگرنه زیرِ نوار می‌رود. `.jalali-date-popover` حالا ۳۰ است.
- **پنجره‌ی زنده‌ی Electron کهنه می‌ماند** وقتی کامپوننتی به فایلِ تازه می‌رود و Fast Refresh آن را
  نمی‌بیند. `touch desktop/index.html` بارگذاریِ کامل را مجبور می‌کند. آرش همین را دید: «هیچ تغییری
  نشون نمیده».
- **Prettier را روی فایل‌های بزرگ اجرا نکن.** یک‌بار کلِ `JournalEntryForm` را بازقالب کرد. ویرایش
  باید جراحی باشد.
- **ویرایش با پایتون** باید `newline=''` داشته باشد. CRLF قاعده‌ی R13ِ ممیز را با خطای دروغین
  می‌شکند.
- **oxlint `only-export-components`:** تابعِ خالص کنارِ کامپوننت صادر نشود. به `lib/` برود
  (`balanceState` همین‌طور رفت).
- **`.page.panels > *`** پس‌زمینه‌ی فرزندِ مستقیم را بازنویسی می‌کند. برای جزئیات cubita-page §۲ را
  ببین.
- **برگه‌ی پهن‌تر از قاب (ماتریس):** `useColumnWidths`ِ «جا در قاب» را نگذار؛ جدول عرضِ **صریح** (جمعِ ستون‌ها)
  بگیرد نه `max-content` — وگرنه ستونِ `ef-col-min` (`width: 1%`) جمع می‌شود و ستونِ ثابتِ کناری روی ستونِ بعد
  می‌نشیند (آرش همین را در بودجه دید). ستون‌های «ردیف» و «حساب» با `position: sticky` ثابت، و نوار بی `columns`.
- **ذخیره‌ی اتمی (سرور دسته را یک‌جا می‌پذیرد یا رد می‌کند):** ذخیره‌ی ردیف‌به‌ردیفِ §۸ این‌جا صدق نمی‌کند. همه‌ی
  سنجش‌ها را پیش از ارسال در `lib/` انجام بده (حلقه، نوعِ نهایی) و خطای سرور را با نامِ «»دارِ پیامش به ردیف
  برگردان (`errorAccountId` در `reclassifySheet.ts`). و **سرویسِ دسته‌ای را با `autoflush=False` بیازما**:
  `SessionLocal` بی autoflush است ولی Sessionِ pytest دارد، پس کوئری‌ای که وسطِ دسته تغییرهای قبلی را نمی‌بیند
  در آزمون سبز و در production غلط است (باگِ `reclassify_accounts` که همین‌جا پیدا شد).
- **موبایلِ برگه‌ای که خانه‌ی ویرایشی‌اش ستونِ چهارم است:** ستون‌های کم‌اهمیت را زیرِ ۷۶۰ پنهان کن (`rx-mhide`)
  تا نام و خانه‌ی ویرایشی بی‌لغزش در قاب باشند؛ برگه‌ای که فقط لغزش دارد، کارِ اصلی‌اش بیرونِ قاب است.
- **Playwright:** وقتی صفحه دو فرم دارد، لوکیتور را با `form:has(.xx-sheet)` محدود کن.
- **سقفِ ورود** ۱۰ بار در ۵ دقیقه است. برای ادامه‌ی آزمایش، uvicornِ :8000 را ری‌استارت کن.

## ۱۱. راستی‌آزمایی — پیش از «تمام شد»

1. `npx tsc -b --force`، `npx oxlint src`، `node scripts/audit-pages.mjs` (۰ خطا)،
   `npx vitest run` (تستِ `lib/<page>Sheet.test.ts` و تستِ رندرِ صفحه)، و `pytest -q` در بک‌اند.
2. **مرورگر، با داده‌ی نمونه و بی دست‌زدن به دیتابیس.** درخواست‌های نوشتنی را با `page.route`
   رهگیری کن و بدنه‌شان را بسنج. این چهار حالت را بگیر: ۱۴۴۰ روشن، ۱۴۴۰ تیره، ۱۲۰۰، ۳۹۰. برای هر
   حالت بسنج:
   - **هم‌خطی:** لبه‌ی هر خانه‌ی نوار منهای لبه‌ی `th`ِ متناظر باید **۰px** باشد:
     ```js
     const r = (el) => el.getBoundingClientRect()
     const th = (id) => r(form.querySelector(`.xx-sheet thead tr:first-child > th[data-col="${id}"]`))
     const d = (a, b) => [Math.round(a.right - b.right), Math.round(a.left - b.left)]
     d(r(form.querySelector('.jb-stat--a')), th('rate'))   // باید [0, 0] باشد
     ```
   - **سرریز:** `scrollWidth - clientWidth` باید ۰ باشد.
   - **کنسول:** خطا نباشد، جز خطای عمدیِ آزمون (مثلاً ۴۰۹).
   - **صفحه‌کلید:** بعد از Enter، `document.activeElement.closest('[data-cell]').dataset.cell` همان
     خانه‌ی موردِ انتظار باشد.
3. بعد از آزمون، uvicornِ آزمونی روی :8000 را ببند. سرورهای توسعه‌ی نسخه‌ی سازمانی را باز بگذار.
4. ردیفِ §۱۰ در `PROJECT_OVERVIEW.md` و خطِ تاریخچه در `AGENT_CLAIMS.md` را بنویس. اگر رفتار عوض شد،
   راهنمای صفحه در `HelpPage.tsx` را هم به‌روز کن. **جدولِ «وضعیت» بالای همین سند را هم به‌روز کن.**

## ۱۲. ترتیبِ کار برای هر صفحه

1. صفحه‌ی فعلی و محدودیت‌های بک‌اندش را بخوان: چه چیز ساخته، ویرایش و حذف می‌شود.
2. الگو را انتخاب کن (بخشِ ۱). اگر با این کار فهرستِ جدا تکراری می‌شود، همین‌جا تصمیمش را بگیر.
3. منطقِ خالص را به `lib/` ببر و تستش را بنویس.
4. گرید را با قطعه‌های بخشِ ۲ بساز: ستون‌ها، `SLOTS`، نوار و صفحه‌کلید. کلاس‌های `jg-c-*` تازه را در
   App.css بگذار.
5. موبایل را درست کن.
6. راستی‌آزمایی کن (بخشِ ۱۱).
7. PR بده و بعد از merge مستقر کن.
