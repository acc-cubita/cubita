import { useEffect, useRef, useState } from 'react'
import { Layers, Save, UserPlus } from 'lucide-react'
import {
  ADDRESS_TYPE_LABELS,
  CHANNEL_TYPE_LABELS,
  CREDIT_ACTION_LABELS,
  GENDER_LABELS,
  MARITAL_STATUS_LABELS,
  TAX_MINISTRY_CLASS_LABELS,
  addContactAddress,
  addContactChannel,
  checkTafsiliTitleTaken,
  createContact,
  createRelatedPerson,
  fetchContactAddresses,
  fetchContactChannels,
  fetchContactGroups,
  fetchContactTafsiliRequirement,
  fetchContacts,
  fetchRelatedPersons,
  deleteContactAddress,
  deleteContactChannel,
  deleteRelatedPerson,
  fetchEmployees,
  fetchGeoLocations,
  updateContact,
  type ContactGroupRecord,
  type ContactRecord,
  type EmployeeRecord,
  type GeoLocationRecord,
  type TafsiliRequirement,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { ActionBar, FormStatus } from '../../components/form/FormKit'
import type { PageKey } from '../../lib/navModel'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * «طرف حساب جدید» — شناسنامه‌ی کاملِ طرف‌حساب.
 *
 * ساختارش از فرمِ سپیدار گرفته شده (سرصفحه + تب‌ها) با سه انحرافِ عمدی که همه یک
 * دلیل دارند — **دو نمای یک داده نساز**:
 *
 *  ۱. **کد و عنوانِ تفصیلی ستونِ طرف‌حساب نیستند**؛ به `analytic_accounts` وصل
 *     می‌شوند. اینکه فیلد اصلاً دیده شود به سطحِ اجبارِ تفصیلی بستگی دارد
 *     (تنظیمات ← شخصی‌سازی).
 *  ۲. **تبِ کارمند فقط پیوند می‌دهد**؛ حکم و تاریخِ استخدام در حقوق و دستمزد
 *     می‌مانند. ولی مشخصاتِ *شخصی* (جنسیت، تأهل، تحصیلات) این‌جاست، چون واقعیتِ
 *     آدم است نه شغلش و مشتریِ غیرکارمند هم می‌تواند داشته باشدش.
 *  ۳. **واسطه و سهامدار پرچمِ مستقل‌اند**، نه مقدارِ تازه‌ی `type` — ده‌ها فیلتر و
 *     گزارش روی (مشتری/تأمین‌کننده/هردو) تکیه دارند.
 *
 * قاعده‌ی خواندنِ فرمِ سپیدار: «(۲)» یعنی فیلدِ دومِ اختیاری (معمولاً لاتین) و «*»
 * یعنی اجباری.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

/** یک ردیفِ در حالِ ساخت — تا پیش از ثبتِ طرف‌حساب شناسه‌ای برای چسبیدن ندارد. */
//: `id` فقط روی ردیف‌هایی هست که از سرور آمده‌اند. نبودنش یعنی «تازه است» —
//: همین یک فیلد، تفاضلِ حالتِ ویرایش را ممکن می‌کند (تازه‌ها POST، رفته‌ها DELETE).
type DraftAddress = { id?: string; address_type: string; title: string; address: string; postal_code: string; route_code: string; is_primary: boolean }
type DraftPhone = { id?: string; channel_type: string; label: string; value: string; is_primary: boolean }
type DraftPerson = { id?: string; name: string; role: string; name2: string; role2: string; phone: string; email: string; is_primary: boolean }

type Msg = { text: string; kind: 'ok' | 'err' } | null

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

export function ContactNewPage({
  token,
  onNavigate,
  contactId,
}: {
  token: string
  onNavigate: (page: PageKey) => void
  /** پر بودنش یعنی **حالتِ ویرایش** — همین فرم، با رکوردِ موجود.
   *
   *  تا امروز این فرم فقط می‌ساخت. یعنی هر چیزی که فقط این‌جا پرسیده می‌شود —
   *  نقشِ سهامدار و درصدِ سهم، واسطه و پورسانت، گروه، محلِ جغرافیایی، کدِ
   *  تفصیلی، نرخِ تخفیف — پس از ساخت **برای همیشه** قفل می‌شد. */
  contactId?: string
}) {
  const isEdit = !!contactId
  const [loading, setLoading] = useState(false)
  //: عکسِ ردیف‌های فرزند در لحظه‌ی بارگذاری. هرچه در این باشد و در فرم نباشد،
  //: کاربر حذفش کرده — و باید واقعاً از سرور برود.
  const loadedChildIds = useRef<{ addresses: string[]; phones: string[]; people: string[] }>({
    addresses: [], phones: [], people: [],
  })
  const [groups, setGroups] = useState<ContactGroupRecord[]>([])
  const [locations, setLocations] = useState<GeoLocationRecord[]>([])
  const [employees, setEmployees] = useState<EmployeeRecord[]>([])
  const [tafsili, setTafsili] = useState<TafsiliRequirement | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<'contact' | 'roles' | 'addresses' | 'phones' | 'people' | 'employee'>('contact')

  // ── هویت ──
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [firstName2, setFirstName2] = useState('')
  const [lastName2, setLastName2] = useState('')
  const [companyName, setCompanyName] = useState('')
  //: **هیچ نقشی پیش‌فرض تیک نیست.** قبلاً «مشتری» از پیش تیک بود و نتیجه‌اش این
  //: می‌شد که کاربر فقط «کارمند» را می‌زد و طرف‌حساب مشتری ثبت می‌شد — نقشی که
  //: هیچ‌وقت انتخاب نکرده بود. راحتیِ یک تیک به قیمتِ داده‌ی غلط نمی‌ارزد.
  const [isCustomer, setIsCustomer] = useState(false)
  const [isSupplier, setIsSupplier] = useState(false)
  const [subType, setSubType] = useState('')
  const [entityType, setEntityType] = useState<'real' | 'legal'>('real')
  const [isActive, setIsActive] = useState(true)
  const [isBlacklisted, setIsBlacklisted] = useState(false)
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [website, setWebsite] = useState('')
  const [address, setAddress] = useState('')
  const [nationalId, setNationalId] = useState('')
  const [economicCode, setEconomicCode] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [registrationNo, setRegistrationNo] = useState('')
  const [passportNo, setPassportNo] = useState('')
  const [birthday, setBirthday] = useState('')
  const [marriageDate, setMarriageDate] = useState('')
  const [groupId, setGroupId] = useState('')
  const [geoId, setGeoId] = useState('')

  // ── تفصیلی ──
  const [tafsiliCode, setTafsiliCode] = useState('')
  const [tafsiliTitle, setTafsiliTitle] = useState('')
  const [tafsiliTitle2, setTafsiliTitle2] = useState('')
  //: کاربر عنوان را دستی عوض کرده؟ اگر نه، با هر تایپِ نام دوباره پیشنهاد می‌شود.
  const [titleTouched, setTitleTouched] = useState(false)
  const [titleTaken, setTitleTaken] = useState(false)

  // ── نقش‌ها ──
  const [discountRate, setDiscountRate] = useState('')
  const [creditLimit, setCreditLimit] = useState('')
  const [creditAction, setCreditAction] = useState('none')
  const [taxClass, setTaxClass] = useState('normal')
  const [isBroker, setIsBroker] = useState(false)
  const [commissionRate, setCommissionRate] = useState('')
  const [isShareholder, setIsShareholder] = useState(false)
  const [sharePercent, setSharePercent] = useState('')
  const [openingAr, setOpeningAr] = useState('')
  const [openingArSide, setOpeningArSide] = useState('debit')
  const [openingAp, setOpeningAp] = useState('')
  const [openingApSide, setOpeningApSide] = useState('credit')

  // ── مشخصاتِ شخصی ──
  const [isEmployee, setIsEmployee] = useState(false)
  const [employeeId, setEmployeeId] = useState('')
  const [gender, setGender] = useState('')
  const [maritalStatus, setMaritalStatus] = useState('')
  const [maritalDate, setMaritalDate] = useState('')
  const [childrenCount, setChildrenCount] = useState('')
  const [dependentsCount, setDependentsCount] = useState('')
  const [educationLevel, setEducationLevel] = useState('')
  const [educationField, setEducationField] = useState('')

  // ── ردیف‌های در حالِ ساخت ──
  const [addresses, setAddresses] = useState<DraftAddress[]>([])
  const [phones, setPhones] = useState<DraftPhone[]>([])
  const [people, setPeople] = useState<DraftPerson[]>([])

  //: **بارگذاریِ حالتِ ویرایش.** طرف‌حساب از همان فهرست می‌آید (اندپوینتِ تکی
  //: ندارد) و ردیف‌های فرزند هرکدام از اندپوینتِ خودشان. `loadTafsili` در این
  //: حالت صدا زده نمی‌شود، وگرنه کدِ تفصیلیِ ذخیره‌شده با کدِ بعدیِ سرور
  //: بازنویسی می‌شد.
  useEffect(() => {
    if (!contactId) return
    let alive = true
    setLoading(true)
    void (async () => {
      try {
        const [all, addrs, chans, persons] = await Promise.all([
          fetchContacts(token),
          fetchContactAddresses(token, contactId).catch(() => []),
          fetchContactChannels(token, contactId).catch(() => []),
          fetchRelatedPersons(token, contactId).catch(() => []),
        ])
        const c = all.find((x) => x.id === contactId)
        if (!alive) return
        if (!c) {
          setMsg({ text: 'این طرف حساب پیدا نشد.', kind: 'err' })
          return
        }
        fillFrom(c)
        setAddresses(addrs.map((a): DraftAddress => ({
          id: a.id,
          address_type: a.address_type ?? '',
          title: a.title ?? '',
          address: a.address ?? '',
          postal_code: a.postal_code ?? '',
          route_code: a.route_code ?? '',
          is_primary: !!a.is_primary,
        })))
        setPhones(chans.filter((ch) => ch.kind === 'phone').map((ch): DraftPhone => ({
          id: ch.id,
          channel_type: ch.channel_type ?? '',
          label: ch.label ?? '',
          value: ch.value,
          is_primary: !!ch.is_primary,
        })))
        loadedChildIds.current = {
          addresses: addrs.map((a) => a.id),
          phones: chans.filter((ch) => ch.kind === 'phone').map((ch) => ch.id),
          people: persons.map((pr) => pr.id),
        }
        setPeople(persons.map((pr): DraftPerson => ({
          id: pr.id,
          name: pr.name,
          role: pr.role ?? '',
          name2: pr.name2 ?? '',
          role2: pr.role2 ?? '',
          phone: pr.phone ?? '',
          email: pr.email ?? '',
          is_primary: !!pr.is_primary,
        })))
      } catch (err) {
        if (alive) setMsg({ text: errText(err), kind: 'err' })
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [token, contactId])

  useEffect(() => {
    void fetchContactGroups(token).then((g) => setGroups(g.filter((x) => x.is_active))).catch(() => {})
    void fetchGeoLocations(token).then((l) => setLocations(l.filter((x) => x.is_active))).catch(() => {})
    void fetchEmployees(token).then((e) => setEmployees(e.filter((x) => x.is_active))).catch(() => {})
    //: در ویرایش، کدِ تفصیلیِ خودِ رکورد مبناست؛ کدِ پیشنهادیِ سرور آن را
    //: بازمی‌نوشت و کاربر بی‌خبر کدِ طرف‌حسابش را عوض می‌کرد.
    if (!contactId) void loadTafsili()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, contactId])

  /** پر کردنِ فرم از رکوردِ موجود — هر فیلدی که فرم می‌فرستد، این‌جا برمی‌گردد.
   *
   *  اگر فیلدی این‌جا جا بیفتد، ویرایش آن را **صفر می‌کند**: فرم مقدارِ خالی را
   *  می‌فرستد و `PATCH` آن را می‌نویسد. پس این تابع باید آینه‌ی کاملِ `submit` بماند. */
  function fillFrom(c: ContactRecord) {
    setFirstName(c.first_name ?? '')
    setLastName(c.last_name ?? '')
    setFirstName2(c.first_name2 ?? '')
    setLastName2(c.last_name2 ?? '')
    //: نامِ شرکت در رکورد همان `name` است؛ برای شخصِ حقیقی از نام و نام خانوادگی
    //: ساخته می‌شود، پس فقط برای حقوقی برمی‌گردد.
    setCompanyName(c.entity_type === 'legal' ? c.name : '')
    setEntityType((c.entity_type ?? 'real') as typeof entityType)
    setIsCustomer(!!c.is_customer)
    setIsSupplier(!!c.is_supplier)
    setSubType(c.sub_type ?? '')
    setIsActive(c.is_active)
    setIsBlacklisted(!!c.is_blacklisted)
    setPhone(c.phone ?? '')
    setEmail(c.email ?? '')
    setWebsite(c.website ?? '')
    setAddress(c.address ?? '')
    setNationalId(c.national_id ?? '')
    setEconomicCode(c.economic_code ?? '')
    setPostalCode(c.postal_code ?? '')
    setRegistrationNo(c.registration_no ?? '')
    setPassportNo(c.passport_no ?? '')
    setBirthday(c.birthday ?? '')
    setMarriageDate(c.marriage_date ?? '')
    setGroupId(c.group_id ?? '')
    setGeoId(c.geo_location_id ?? '')
    setCreditLimit(String(Number(c.credit_limit) || ''))
    setCreditAction((c.credit_action ?? 'warn') as typeof creditAction)
    setDiscountRate(String(Number(c.discount_rate) || ''))
    setTaxClass((c.tax_ministry_class ?? '') as typeof taxClass)
    setIsBroker(!!c.is_broker)
    setCommissionRate(String(Number(c.commission_rate) || ''))
    setIsShareholder(!!c.is_shareholder)
    setSharePercent(String(Number(c.share_percent) || ''))
    setIsEmployee(!!c.is_employee)
    setEmployeeId(c.employee_id ?? '')
    setGender(c.gender ?? '')
    setMaritalStatus(c.marital_status ?? '')
    setMaritalDate(c.marital_status_date ?? '')
    setChildrenCount(String(Number(c.children_count) || ''))
    setDependentsCount(String(Number(c.dependents_count) || ''))
    setEducationLevel(c.education_level ?? '')
    setEducationField(c.education_field ?? '')
    setTafsiliCode(c.tafsili_code ?? '')
    setTafsiliTitle(c.tafsili_title ?? '')
    setTafsiliTitle2(c.tafsili_title2 ?? '')
    setTitleTouched(true)
    //: **ماندهٔ اول دوره عمداً برنمی‌گردد.** آن سندِ افتتاحیه را می‌زند و یک‌بار
    //: ثبت می‌شود؛ برگرداندنش در فرمِ ویرایش یعنی هر ذخیره، سند را دوباره بزند.
  }

  function loadTafsili() {
    return fetchContactTafsiliRequirement(token)
      .then((r) => {
        setTafsili(r)
        //: کدِ پیشنهادی از سرور می‌آید نه از حدسِ محلی — قاعده آن‌جا تعریف شده.
        if (r.suggested_code) setTafsiliCode(r.suggested_code)
      })
      .catch(() => {})
  }

  /** نامِ نمایشی — سرور هم همین را می‌سازد؛ این‌جا برای پیش‌نمایش و اعتبارسنجی. */
  const displayName =
    entityType === 'legal'
      ? companyName.trim()
      : [firstName.trim(), lastName.trim()].filter(Boolean).join(' ')

  /**
   * پنج تیک → یک ستونِ `type`.
   *
   * `contacts.type` فقط سه مقدار دارد (مشتری/تأمین‌کننده/هردو) و فیلترها و
   * شاخص‌های موجود روی همان تکیه دارند؛ واسطه، سهامدار و کارمند پرچمِ جداگانه‌اند.
   * پس نقش‌ها مستقل تیک می‌خورند و این‌جا به آن ستون نگاشته می‌شوند.
   *
   * **تا مهاجرتِ ۰۱۶۴ این‌جا یک نگاشتِ پنهان بود.** طرف‌حسابی که هیچ‌یک از دو
   * نقشِ معاملاتی را نداشت (فقط واسطه، سهامدار یا کارمند) به‌زور «تأمین‌کننده»
   * ثبت می‌شد، چون ستونِ `type` حالتِ چهارمی نداشت. کاربر واسطه می‌ساخت و در
   * فهرست «تأمین‌کننده، واسطه» می‌دید — و در انتخابگرِ تأمین‌کننده‌ی رسیدِ انبار
   * هم ظاهر می‌شد.
   *
   * حالا فرم **خودِ پرچم‌ها را می‌فرستد** و هیچ نگاشتی در کار نیست. `type` فقط
   * برای فراخوان‌های قدیمیِ سرور مشتق می‌شود؛ روتر وقتی پرچم‌ها بیایند کنارش
   * می‌گذارد.
   */
  const contactType = isCustomer && isSupplier ? 'both' : isCustomer ? 'customer'
    : isSupplier ? 'supplier' : 'none'
  const hasAnyRole = isCustomer || isSupplier || isBroker || isShareholder || isEmployee

  //: عنوانِ تفصیلی از نام پیشنهاد می‌شود تا کاربر همان را دوباره تایپ نکند — ولی
  //: لحظه‌ای که خودش دستش را رویش گذاشت، دیگر بازنویسی نمی‌شود.
  useEffect(() => {
    if (!titleTouched) setTafsiliTitle(displayName)
  }, [displayName, titleTouched])

  //: تکراری بودنِ عنوان **ثبت را نمی‌بندد** — دو نفرِ هم‌نام واقعاً ممکن‌اند — ولی
  //: کاربر باید بداند تا چیزی به آن اضافه کند، وگرنه در فهرستِ تفصیلی گم می‌شود.
  useEffect(() => {
    const title = tafsiliTitle.trim()
    if (!title) {
      setTitleTaken(false)
      return
    }
    let alive = true
    const timer = setTimeout(() => {
      void checkTafsiliTitleTaken(token, title)
        .then((r) => { if (alive) setTitleTaken(r.taken) })
        .catch(() => { if (alive) setTitleTaken(false) })
    }, 350)
    return () => { alive = false; clearTimeout(timer) }
  }, [token, tafsiliTitle])

  function reset() {
    setFirstName(''); setLastName(''); setFirstName2(''); setLastName2(''); setCompanyName('')
    setPhone(''); setEmail(''); setWebsite(''); setAddress('')
    setNationalId(''); setEconomicCode(''); setPostalCode('')
    setRegistrationNo(''); setPassportNo(''); setBirthday(''); setMarriageDate('')
    setIsCustomer(true); setIsSupplier(false); setIsBroker(false); setIsShareholder(false)
    setCreditLimit(''); setDiscountRate(''); setCommissionRate(''); setSharePercent('')
    setTafsiliTitle(''); setTafsiliTitle2(''); setTitleTouched(false); setTitleTaken(false)
    setEmployeeId(''); setGender(''); setMaritalStatus(''); setMaritalDate('')
    setChildrenCount(''); setDependentsCount(''); setEducationLevel(''); setEducationField('')
    setOpeningAr(''); setOpeningAp('')
    setAddresses([]); setPhones([]); setPeople([])
    //: کدِ بعدی دوباره از سرور، وگرنه ثبتِ دومِ پشتِ‌هم کدِ تکراری می‌فرستد.
    void loadTafsili()
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!displayName) {
      setMsg({ text: 'نامِ طرف حساب را وارد کنید.', kind: 'err' })
      document.querySelector<HTMLInputElement>('.ef-form input')?.focus()
      return
    }
    if (!displayName) return
    //: بی‌نقش یعنی طرف‌حسابی که هیچ‌جا به کار نمی‌آید — نه در فاکتور دیده می‌شود نه
    //: در فهرستِ واسطه‌ها. بهتر است همین‌جا بگوییم تا کاربر بعداً دنبالش نگردد.
    if (!hasAnyRole) {
      setTab('roles')
      setMsg({ text: 'دستِ‌کم یک نقش انتخاب کنید: مشتری، تأمین‌کننده، واسطه، سهامدار یا کارمند.', kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const payload = {
        name: displayName,
        type: contactType,
        is_customer: isCustomer,
        is_supplier: isSupplier,
        first_name: entityType === 'real' ? firstName.trim() : '',
        last_name: entityType === 'real' ? lastName.trim() : '',
        first_name2: firstName2.trim(),
        last_name2: lastName2.trim(),
        sub_type: subType.trim(),
        phone: phone.trim() || null,
        email: email.trim() || null,
        website: website.trim(),
        address,
        tax_id: null,
        entity_type: entityType,
        national_id: nationalId.trim() || null,
        economic_code: economicCode.trim() || null,
        postal_code: postalCode.trim() || null,
        registration_no: registrationNo.trim() || null,
        passport_no: passportNo.trim() || null,
        birthday: birthday || null,
        marriage_date: marriageDate || null,
        is_blacklisted: isBlacklisted,
        group_id: groupId || null,
        geo_location_id: geoId || null,
        credit_limit: Number(creditLimit) || 0,
        credit_action: creditAction,
        discount_rate: Number(discountRate) || 0,
        tax_ministry_class: taxClass,
        is_broker: isBroker,
        commission_rate: Number(commissionRate) || 0,
        is_shareholder: isShareholder,
        share_percent: Number(sharePercent) || 0,
        is_employee: isEmployee,
        employee_id: employeeId || null,
        gender,
        marital_status: maritalStatus,
        marital_status_date: maritalDate || null,
        children_count: Number(childrenCount) || 0,
        dependents_count: Number(dependentsCount) || 0,
        education_level: educationLevel.trim(),
        education_field: educationField.trim(),
        //: مانده‌ی نقشی که تیک نخورده صفر می‌رود، حتی اگر کاربر قبلاً عددی تایپ
        //: کرده و بعد تیک را برداشته باشد — وگرنه عددِ یک نقشِ نداشته در سندِ
        //: افتتاحیه می‌نشست.
        opening_ar_amount: isCustomer ? Number(openingAr) || 0 : 0,
        opening_ar_side: openingArSide,
        opening_ap_amount: isSupplier ? Number(openingAp) || 0 : 0,
        opening_ap_side: openingApSide,
        //: در «شناور» سرور اینها را نادیده می‌گیرد، پس فرستادنشان بی‌خطر است.
        tafsili_code: tafsiliCode.trim() || null,
        tafsili_title: tafsiliTitle.trim() || null,
        tafsili_title2: tafsiliTitle2.trim(),
      }

      //: **در ویرایش ماندهٔ اول دوره فرستاده نمی‌شود.** آن سندِ افتتاحیه را
      //: می‌زند و یک‌بار ثبت می‌شود؛ فرستادنش در هر ذخیره یعنی سندِ تکراری.
      if (isEdit) {
        const { opening_ar_amount, opening_ar_side, opening_ap_amount, opening_ap_side, ...editable } = payload
        void opening_ar_amount; void opening_ar_side; void opening_ap_amount; void opening_ap_side
        await updateContact(token, contactId!, editable)

        //: **ردیف‌های فرزند هم باید بروند.** تا پیش از این، `submit` در ویرایش
        //: همین‌جا برمی‌گشت: کاربر نشانی اضافه می‌کرد، پیامِ «به‌روز شد»
        //: می‌گرفت، و ردیفش **بی‌صدا دور ریخته می‌شد**. اندپوینت‌ها فقط
        //: POST/DELETE دارند (نه PATCH) و تب‌ها ویرایشِ درجا ندارند، پس تفاضلِ
        //: شناسه کافی است: بی‌شناسه‌ها تازه‌اند، شناسه‌های غایب حذف شده‌اند.
        const failed: string[] = []
        const kept = {
          addresses: new Set(addresses.map((a) => a.id).filter(Boolean) as string[]),
          phones: new Set(phones.map((x) => x.id).filter(Boolean) as string[]),
          people: new Set(people.map((x) => x.id).filter(Boolean) as string[]),
        }
        for (const id of loadedChildIds.current.addresses.filter((i) => !kept.addresses.has(i))) {
          try { await deleteContactAddress(token, contactId!, id) } catch { failed.push('حذفِ نشانی') }
        }
        for (const id of loadedChildIds.current.phones.filter((i) => !kept.phones.has(i))) {
          try { await deleteContactChannel(token, contactId!, id) } catch { failed.push('حذفِ تلفن') }
        }
        for (const id of loadedChildIds.current.people.filter((i) => !kept.people.has(i))) {
          try { await deleteRelatedPerson(token, id) } catch { failed.push('حذفِ فردِ مرتبط') }
        }
        for (const a of addresses.filter((x) => !x.id)) {
          try { await addContactAddress(token, contactId!, a) } catch { failed.push(a.address || a.title) }
        }
        for (const x of phones.filter((y) => !y.id)) {
          try { await addContactChannel(token, contactId!, { kind: 'phone', ...x }) } catch { failed.push(x.value) }
        }
        for (const x of people.filter((y) => !y.id)) {
          try { await createRelatedPerson(token, { contact_id: contactId!, ...x }) } catch { failed.push(x.name) }
        }

        setMsg({
          text: failed.length
            ? `طرف‌حساب «${displayName}» به‌روز شد، ولی این ردیف‌ها ثبت/حذف نشدند: ${failed.join('، ')}`
            : `طرف‌حساب «${displayName}» به‌روز شد.`,
          kind: failed.length ? 'err' : 'ok',
        })
        setBusy(false)
        return
      }

      const created = await createContact(token, payload)

      //: ردیف‌های فرزند به شناسه نیاز دارند، پس پس از ساختِ طرف‌حساب می‌روند.
      //: شکستِ یکی نباید ثبتِ خودِ طرف‌حساب را باطل جلوه دهد، پس جدا گزارش می‌شود.
      const failed: string[] = []
      for (const a of addresses) {
        try { await addContactAddress(token, created.id, a) } catch { failed.push(a.address || a.title) }
      }
      for (const p of phones) {
        try { await addContactChannel(token, created.id, { kind: 'phone', ...p }) } catch { failed.push(p.value) }
      }
      for (const p of people) {
        try { await createRelatedPerson(token, { contact_id: created.id, ...p }) } catch { failed.push(p.name) }
      }

      setMsg({
        text: failed.length
          ? `طرف‌حساب «${displayName}» ساخته شد، ولی این ردیف‌ها ثبت نشدند: ${failed.join('، ')}`
          : `طرف‌حساب «${displayName}» ساخته شد.`,
        kind: failed.length ? 'err' : 'ok',
      })
      if (!failed.length) reset()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const showTafsili = tafsili != null && tafsili.requirement !== 'hidden'

  return (
    <div className="page panels">
      <PageHeader
        icon={UserPlus}
        title={isEdit ? 'ویرایش طرف حساب' : 'طرف حساب جدید'}
        description="شناسنامه‌ی مشتری، تأمین‌کننده، واسطه یا سهامدار — با نشانی‌های ارسال، تلفن‌ها، افرادِ مرتبط و کدِ تفصیلی."
      />

      <div className="ef-form">
      {loading && <p className="muted">در حال بارگذاری…</p>}

      <form noValidate onSubmit={(e) => void submit(e)}>
        <SectionCard
          icon={UserPlus}
          title="مشخصات اصلی"
          description={
            entityType === 'legal'
              ? 'شخصِ حقوقی: نامِ شرکت و شناسه‌ی ملی.'
              : 'شخصِ حقیقی: نام و نام خانوادگی جدا ثبت می‌شوند و نامِ نمایشی از آن‌ها ساخته می‌شود.'
          }
        >
          <div className="cmp-form">
            <label>
              <span>نوع شخص</span>
              <SearchSelect value={entityType} onChange={(e) => setEntityType(e.target.value as 'real' | 'legal')}>
                <option value="real">حقیقی</option>
                <option value="legal">حقوقی</option>
              </SearchSelect>
            </label>
            <label>
              <span>نوع فرعی</span>
              <input value={subType} onChange={(e) => setSubType(e.target.value)} placeholder="سایر" maxLength={50} />
            </label>

            {entityType === 'legal' ? (
              <label className="cmp-form-wide">
                <span>نام شرکت</span>
                <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required maxLength={200} />
              </label>
            ) : (
              <>
                <label>
                  <span>نام</span>
                  <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={100} />
                </label>
                <label>
                  <span>نام خانوادگی</span>
                  <input value={lastName} onChange={(e) => setLastName(e.target.value)} maxLength={100} />
                </label>
              </>
            )}

            <label>
              <span>نام (۲)</span>
              <input value={firstName2} onChange={(e) => setFirstName2(e.target.value)} dir="ltr" maxLength={100} />
            </label>
            <label>
              <span>نام خانوادگی (۲)</span>
              <input value={lastName2} onChange={(e) => setLastName2(e.target.value)} dir="ltr" maxLength={100} />
            </label>

            <label>
              <span>{entityType === 'legal' ? 'شناسه ملی' : 'کد ملی'}</span>
              <input value={nationalId} onChange={(e) => setNationalId(e.target.value)} maxLength={20} />
            </label>
            <label>
              <span>کد اقتصادی</span>
              <input value={economicCode} onChange={(e) => setEconomicCode(e.target.value)} maxLength={20} />
            </label>
            {entityType === 'legal' ? (
              <label>
                <span>شماره ثبت</span>
                <input value={registrationNo} onChange={(e) => setRegistrationNo(e.target.value)} maxLength={50} />
              </label>
            ) : (
              <label>
                <span>شماره گذرنامه</span>
                <input value={passportNo} onChange={(e) => setPassportNo(e.target.value)} maxLength={50} />
              </label>
            )}

            <label className="fy-check">
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
              فعال
            </label>
            {/* لیستِ سیاه جدا از «فعال» است: غیرفعال یعنی «دیگر کار نمی‌کنیم»،
                لیستِ سیاه یعنی «کار می‌کنیم ولی با احتیاط». پس هشدار می‌دهد و
                جلوی فاکتور را نمی‌گیرد — اگر می‌گرفت، کاربر برای راه‌افتادنِ کارش
                تیک را برمی‌داشت و نشانه برای همیشه از بین می‌رفت. */}
            <label className="fy-check">
              <input type="checkbox" checked={isBlacklisted} onChange={(e) => setIsBlacklisted(e.target.checked)} />
              لیست سیاه
            </label>
            <span className="field-hint cmp-form-wide">
              هنگام صدور فاکتور برای این طرف حساب هشدار داده می‌شود، ولی ثبت بسته نمی‌شود.
            </span>
          </div>
        </SectionCard>

        {showTafsili && (
          <SectionCard
            icon={Layers}
            title="تفصیلی"
            description={
              tafsili?.requirement === 'required'
                ? 'سطحِ اجبارِ تفصیلی روی «اجباری» است، پس این طرف‌حساب حتماً تفصیلی می‌گیرد.'
                : 'سطحِ اجبارِ تفصیلی روی «ترکیبی» است — دادنِ تفصیلی اختیاری است. (تنظیمات ← شخصی‌سازی)'
            }
          >
            <div className="cmp-form">
              <label>
                <span>کد تفصیلی</span>
                <input value={tafsiliCode} onChange={(e) => setTafsiliCode(e.target.value)} dir="ltr" maxLength={20} />
                <span className="field-hint">
                  خالی بگذارید تا خودکار ساخته شود؛ عددِ پیشنهادی اولین کدِ آزاد است.
                </span>
              </label>
              <label>
                <span>عنوان تفصیلی</span>
                <input
                  value={tafsiliTitle}
                  onChange={(e) => { setTitleTouched(true); setTafsiliTitle(e.target.value) }}
                  className={titleTaken ? 'input-warn' : undefined}
                  maxLength={200}
                />
                <span className={titleTaken ? 'field-hint field-hint--warn' : 'field-hint'}>
                  {titleTaken
                    ? 'این عنوان از قبل استفاده شده — چیزی به آن اضافه کنید تا در فهرستِ تفصیلی قابلِ تشخیص باشد.'
                    : 'از نام و نام خانوادگی پیشنهاد می‌شود؛ می‌توانید عوضش کنید.'}
                </span>
              </label>
              <label>
                <span>عنوان تفصیلی (۲)</span>
                <input value={tafsiliTitle2} onChange={(e) => setTafsiliTitle2(e.target.value)} dir="ltr" maxLength={200} />
              </label>
            </div>
          </SectionCard>
        )}

        <SectionCard icon={UserPlus} title="جزئیات">
          <div className="cc-tabs">
            {([
              ['contact', 'تماس'],
              ['roles', 'نقش‌ها و اعتبار'],
              ['addresses', `نشانی${addresses.length ? ` (${fa(addresses.length)})` : ''}`],
              ['phones', `تلفن${phones.length ? ` (${fa(phones.length)})` : ''}`],
              ['people', `افراد مرتبط${people.length ? ` (${fa(people.length)})` : ''}`],
              ['employee', 'مشخصات کارمند'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={tab === key ? 'is-active' : ''}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'contact' && (
            <ContactTab
              {...{ phone, setPhone, email, setEmail, website, setWebsite, postalCode, setPostalCode,
                    groupId, setGroupId, geoId, setGeoId, groups, locations, address, setAddress,
                    entityType, birthday, setBirthday, marriageDate, setMarriageDate }}
            />
          )}

          {tab === 'roles' && (
            <RolesTab
              {...{ isCustomer, setIsCustomer, isSupplier, setIsSupplier,
                    isEmployee, setIsEmployee,
                    discountRate, setDiscountRate, taxClass, setTaxClass,
                    creditLimit, setCreditLimit, creditAction, setCreditAction,
                    isBroker, setIsBroker, commissionRate, setCommissionRate,
                    isShareholder, setIsShareholder, sharePercent, setSharePercent,
                    openingAr, setOpeningAr, openingArSide, setOpeningArSide,
                    openingAp, setOpeningAp, openingApSide, setOpeningApSide }}
            />
          )}

          {tab === 'addresses' && <AddressesTab rows={addresses} setRows={setAddresses} />}
          {tab === 'phones' && <PhonesTab rows={phones} setRows={setPhones} />}
          {tab === 'people' && <PeopleTab rows={people} setRows={setPeople} />}

          {tab === 'employee' && (
            <EmployeeTab
              {...{ employeeId, setEmployeeId, employees,
                    gender, setGender, maritalStatus, setMaritalStatus,
                    maritalDate, setMaritalDate, childrenCount, setChildrenCount,
                    dependentsCount, setDependentsCount, educationLevel, setEducationLevel,
                    educationField, setEducationField }}
            />
          )}
        </SectionCard>

        <ActionBar
          status={
            <FormStatus
              msg={msg}
              idle={displayName ? `نامِ نمایشی: ${displayName}` : 'نام را وارد کنید تا نامِ نمایشی ساخته شود.'}
            />
          }
        >
          <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('contactlist')}>
            فهرستِ طرف‌حساب‌ها
          </button>
          <button type="submit" className="btn-primary" disabled={busy || loading}>
            <Save size={16} /> {isEdit ? 'ذخیره‌ی تغییرات' : 'ثبتِ طرف حساب'}
          </button>
        </ActionBar>
      </form>
      </div>
    </div>
  )
}

// ── تب‌ها ─────────────────────────────────────────────────────────────────────

type Setter<T> = (v: T) => void

function ContactTab(p: {
  phone: string; setPhone: Setter<string>
  email: string; setEmail: Setter<string>
  website: string; setWebsite: Setter<string>
  postalCode: string; setPostalCode: Setter<string>
  groupId: string; setGroupId: Setter<string>
  geoId: string; setGeoId: Setter<string>
  groups: ContactGroupRecord[]; locations: GeoLocationRecord[]
  address: string; setAddress: Setter<string>
  entityType: 'real' | 'legal'
  birthday: string; setBirthday: Setter<string>
  marriageDate: string; setMarriageDate: Setter<string>
}) {
  return (
    <div className="cmp-form">
      <label>
        <span>تلفن اصلی</span>
        <input value={p.phone} onChange={(e) => p.setPhone(e.target.value)} maxLength={20} />
        <span className="field-hint">شماره‌های دیگر را در تبِ «تلفن» اضافه کنید.</span>
      </label>
      <label>
        <span>ایمیل</span>
        <input value={p.email} onChange={(e) => p.setEmail(e.target.value)} maxLength={150} />
      </label>
      <label>
        <span>آدرس وب‌سایت</span>
        <input value={p.website} onChange={(e) => p.setWebsite(e.target.value)} dir="ltr" maxLength={200} />
      </label>
      <label>
        <span>کد پستی</span>
        <input value={p.postalCode} onChange={(e) => p.setPostalCode(e.target.value)} maxLength={20} />
      </label>
      <label>
        <span>گروه</span>
        <SearchSelect value={p.groupId} onChange={(e) => p.setGroupId(e.target.value)}>
          <option value="">— بدون گروه —</option>
          {p.groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </SearchSelect>
      </label>
      <label>
        <span>محلِ جغرافیایی</span>
        <SearchSelect value={p.geoId} onChange={(e) => p.setGeoId(e.target.value)}>
          <option value="">— تعیین‌نشده —</option>
          {p.locations.map((l) => <option key={l.id} value={l.id}>{l.path}</option>)}
        </SearchSelect>
      </label>
      {p.entityType === 'real' && (
        <>
          <label>
            <span>تاریخ تولد</span>
            <JalaliDatePicker value={p.birthday} onChange={p.setBirthday} />
          </label>
          <label>
            <span>تاریخ ازدواج</span>
            <JalaliDatePicker value={p.marriageDate} onChange={p.setMarriageDate} />
          </label>
        </>
      )}
      <label className="cmp-form-wide">
        <span>نشانی اصلی</span>
        <input value={p.address} onChange={(e) => p.setAddress(e.target.value)} />
        <span className="field-hint">نشانی‌های دیگر (انبار، ارسال کالا…) را در تبِ «نشانی» اضافه کنید.</span>
      </label>
    </div>
  )
}

function RolesTab(p: {
  isCustomer: boolean; setIsCustomer: Setter<boolean>
  isSupplier: boolean; setIsSupplier: Setter<boolean>
  isEmployee: boolean; setIsEmployee: Setter<boolean>
  discountRate: string; setDiscountRate: Setter<string>
  taxClass: string; setTaxClass: Setter<string>
  creditLimit: string; setCreditLimit: Setter<string>
  creditAction: string; setCreditAction: Setter<string>
  isBroker: boolean; setIsBroker: Setter<boolean>
  commissionRate: string; setCommissionRate: Setter<string>
  isShareholder: boolean; setIsShareholder: Setter<boolean>
  sharePercent: string; setSharePercent: Setter<string>
  openingAr: string; setOpeningAr: Setter<string>
  openingArSide: string; setOpeningArSide: Setter<string>
  openingAp: string; setOpeningAp: Setter<string>
  openingApSide: string; setOpeningApSide: Setter<string>
}) {
  return (
    <div className="cmp-form">
      <div className="cmp-form-wide pz-effects-head">نقش‌ها</div>
      {/* چهار نقشِ مستقل، نه یک کشوییِ تک‌انتخابی: یک نفر واقعاً می‌تواند هم‌زمان
          مشتریِ ما، تأمین‌کننده‌ی ما، واسطه‌ی معرفیِ مشتری و سهامدار باشد. */}
      <div className="cmp-form-wide role-picker">
        <label className="fy-check">
          <input type="checkbox" checked={p.isCustomer} onChange={(e) => p.setIsCustomer(e.target.checked)} />
          مشتری
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.isSupplier} onChange={(e) => p.setIsSupplier(e.target.checked)} />
          تأمین‌کننده
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.isBroker} onChange={(e) => p.setIsBroker(e.target.checked)} />
          واسطه
        </label>
        <label className="fy-check">
          <input type="checkbox" checked={p.isShareholder} onChange={(e) => p.setIsShareholder(e.target.checked)} />
          سهامدار
        </label>
        {/* «کارمند» هم نقش است و جایش کنارِ بقیه است، نه در تبِ دیگر. تیکش این‌جاست
            و *پیوند* به رکوردِ حقوق و دستمزد در تبِ «مشخصات کارمند» — یک تیک، یک جا. */}
        <label className="fy-check">
          <input type="checkbox" checked={p.isEmployee} onChange={(e) => p.setIsEmployee(e.target.checked)} />
          کارمند
        </label>
      </div>
      <p className="muted cmp-form-wide">
        واسطه کسی است که معامله را واسطه‌گری می‌کند و پورسانت می‌گیرد — و می‌تواند
        هم‌زمان مشتری یا تأمین‌کننده هم باشد.
        {!p.isCustomer && !p.isSupplier && (p.isBroker || p.isShareholder || p.isEmployee)
          ? ' نقشِ معاملاتی لازم نیست: این طرف‌حساب نه مشتری ثبت می‌شود نه تأمین‌کننده. پرداخت به او (پورسانت، سودِ سهام یا حقوق) همچنان ممکن است.'
          : ''}
      </p>
      {p.isBroker && (
        <label>
          <span>نرخ پورسانت (٪)</span>
          <input type="number" step="0.01" min="0" max="100" value={p.commissionRate}
                 onChange={(e) => p.setCommissionRate(e.target.value)} placeholder="۰" />
          <span className="field-hint">درصدی که بابتِ واسطه‌گری به او می‌رسد.</span>
        </label>
      )}
      {p.isShareholder && (
        <label>
          <span>درصد سهام (٪)</span>
          <input type="number" step="0.01" min="0" max="100" value={p.sharePercent}
                 onChange={(e) => p.setSharePercent(e.target.value)} placeholder="۰" />
        </label>
      )}

      <div className="cmp-form-wide pz-effects-head">تخفیف، مالیات و اعتبار</div>
      <label>
        <span>نرخ تخفیف (٪)</span>
        <input type="number" step="0.01" min="0" max="100" value={p.discountRate}
               onChange={(e) => p.setDiscountRate(e.target.value)} placeholder="۰" />
      </label>
      <label>
        <span>دسته‌بندی وزارت دارایی</span>
        <SearchSelect value={p.taxClass} onChange={(e) => p.setTaxClass(e.target.value)}>
          {Object.entries(TAX_MINISTRY_CLASS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>

      <label>
        <span>سقف اعتبار (ریال)</span>
        <input type="number" value={p.creditLimit} onChange={(e) => p.setCreditLimit(e.target.value)} placeholder="۰ = بدون سقف" />
      </label>
      {/* تا امروز سقفِ اعتبار ذخیره می‌شد ولی هیچ‌جا اعمال نمی‌شد. پیش‌فرضِ «بدون
          کنترل» یعنی سقف‌های ثبت‌شده‌ی قبلی یک‌شبه جلوی فروش را نمی‌گیرند. */}
      <label>
        <span>با عبور از سقف</span>
        <SearchSelect value={p.creditAction} onChange={(e) => p.setCreditAction(e.target.value)}>
          {Object.entries(CREDIT_ACTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>

      {/* مانده‌ی اول دوره فقط دو نقش دارد: حسابِ دریافتنی (مشتری) و پرداختنی
          (تأمین‌کننده). سهامدار و واسطه مانده‌ی اول دوره ندارند — سودِ سهام و
          پورسانت از معامله می‌آیند نه از مانده‌ی ابتدای دوره — و کارمند هم
          مانده‌اش در حقوق و دستمزد است نه این‌جا. پس اگر آن دو نقش تیک نخورده‌اند
          این بخش اصلاً نمی‌آید؛ فیلدی که هیچ‌وقت نباید پر شود نباید دیده شود. */}
      {(p.isCustomer || p.isSupplier) && (
        <div className="cmp-form-wide pz-effects-head">مانده اول دوره</div>
      )}
      {p.isCustomer && (
        <>
          <label>
            <span>به‌عنوانِ مشتری (ریال)</span>
            <input type="number" min="0" value={p.openingAr} onChange={(e) => p.setOpeningAr(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>سمت</span>
            <SearchSelect value={p.openingArSide} onChange={(e) => p.setOpeningArSide(e.target.value)}>
              <option value="debit">بدهکار (به ما بدهکار است)</option>
              <option value="credit">بستانکار (پیش‌دریافت)</option>
            </SearchSelect>
          </label>
        </>
      )}
      {p.isSupplier && (
        <>
          <label>
            <span>به‌عنوانِ تأمین‌کننده (ریال)</span>
            <input type="number" min="0" value={p.openingAp} onChange={(e) => p.setOpeningAp(e.target.value)} placeholder="۰" />
          </label>
          <label>
            <span>سمت</span>
            <SearchSelect value={p.openingApSide} onChange={(e) => p.setOpeningApSide(e.target.value)}>
              <option value="credit">بستانکار (ما به او بدهکاریم)</option>
              <option value="debit">بدهکار (پیش‌پرداخت)</option>
            </SearchSelect>
          </label>
        </>
      )}
      {(p.isCustomer || p.isSupplier) && (
        <p className="muted cmp-form-wide">
          این مبالغ در «سند افتتاحیه» ثبت می‌شوند و پس از صدورِ آن سند دیگر قابلِ تغییر
          نیستند — اصلاحشان با سندِ حسابداری انجام می‌شود.
        </p>
      )}
    </div>
  )
}

function AddressesTab({ rows, setRows }: { rows: DraftAddress[]; setRows: Setter<DraftAddress[]> }) {
  const [draft, setDraft] = useState<DraftAddress>({
    address_type: 'official', title: '', address: '', postal_code: '', route_code: '', is_primary: false,
  })

  function add() {
    if (!draft.address.trim() && !draft.title.trim()) return
    //: «اصلی» فقط یکی — سمتِ سرور هم همین گارد هست، این‌جا فقط فهرست را همسان نگه می‌دارد.
    const next = draft.is_primary ? rows.map((r) => ({ ...r, is_primary: false })) : [...rows]
    setRows([...next, draft])
    setDraft({ address_type: 'official', title: '', address: '', postal_code: '', route_code: '', is_primary: false })
  }

  return (
    <div className="cmp-form">
      <p className="muted cmp-form-wide">
        نشانیِ نوعِ «ارسال کالا» همان است که به مأمورِ ارسال داده می‌شود. «کد مسیر» زونِ
        توزیع است و مشتری‌ها را برای مسیربندی گروه می‌کند.
      </p>
      <label>
        <span>نوع</span>
        <SearchSelect value={draft.address_type} onChange={(e) => setDraft({ ...draft, address_type: e.target.value })}>
          {Object.entries(ADDRESS_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>
      <label>
        <span>عنوان</span>
        <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })}
               placeholder="دفتر مرکزی، انبارِ شرق…" maxLength={150} />
      </label>
      <label className="cmp-form-wide">
        <span>نشانی</span>
        <input value={draft.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} />
      </label>
      <label>
        <span>کد پستی</span>
        <input value={draft.postal_code} onChange={(e) => setDraft({ ...draft, postal_code: e.target.value })} maxLength={20} />
      </label>
      <label>
        <span>کد مسیر (زون)</span>
        <input value={draft.route_code} onChange={(e) => setDraft({ ...draft, route_code: e.target.value })} maxLength={30} />
      </label>
      <label className="fy-check">
        <input type="checkbox" checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
        اصلی
      </label>
      <div className="cmp-form-wide">
        <button type="button" onClick={add} disabled={!draft.address.trim() && !draft.title.trim()}>افزودن نشانی</button>
      </div>

      <div className="cmp-form-wide">
        {rows.length === 0 ? (
          <EmptyState icon={UserPlus} text="هنوز نشانیِ اضافه‌ای وارد نشده — نشانیِ اصلی در تبِ «تماس» است." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr><th>نوع</th><th>عنوان</th><th>نشانی</th><th>کد پستی</th><th>کد مسیر</th><th>اصلی</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.address_type}-${i}`}>
                    <td className="card-title" data-label="نوع">{ADDRESS_TYPE_LABELS[r.address_type]}</td>
                    <td data-label="عنوان">{r.title || '—'}</td>
                    <td className="card-wide" data-label="نشانی">{r.address || '—'}</td>
                    <td data-label="کد پستی">{r.postal_code || '—'}</td>
                    <td data-label="کد مسیر">{r.route_code || '—'}</td>
                    <td data-label="اصلی">{r.is_primary ? 'بله' : '—'}</td>
                    <td className="card-actions">
                      <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))}>حذف</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function PhonesTab({ rows, setRows }: { rows: DraftPhone[]; setRows: Setter<DraftPhone[]> }) {
  const [draft, setDraft] = useState<DraftPhone>({ channel_type: 'office', label: '', value: '', is_primary: false })

  function add() {
    if (!draft.value.trim()) return
    const next = draft.is_primary ? rows.map((r) => ({ ...r, is_primary: false })) : [...rows]
    setRows([...next, { ...draft, value: draft.value.trim() }])
    setDraft({ channel_type: 'office', label: '', value: '', is_primary: false })
  }

  return (
    <div className="cmp-form">
      <p className="muted cmp-form-wide">
        تلفنِ اصلی در تبِ «تماس» است. این‌جا شماره‌های دیگر با نوعشان اضافه می‌شوند.
      </p>
      <label>
        <span>نوع</span>
        <SearchSelect value={draft.channel_type} onChange={(e) => setDraft({ ...draft, channel_type: e.target.value })}>
          {Object.entries(CHANNEL_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>
      <label>
        <span>برچسب</span>
        <input value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })}
               placeholder="شماره مدیر، داخلی ۲۰۴…" maxLength={100} />
      </label>
      <label>
        <span>شماره</span>
        <input value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} />
      </label>
      <label className="fy-check">
        <input type="checkbox" checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
        اصلی
      </label>
      <div className="cmp-form-wide">
        <button type="button" onClick={add} disabled={!draft.value.trim()}>افزودن تلفن</button>
      </div>

      <div className="cmp-form-wide">
        {rows.length === 0 ? (
          <EmptyState icon={UserPlus} text="هنوز شماره‌ی اضافه‌ای وارد نشده." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead><tr><th>نوع</th><th>برچسب</th><th>شماره</th><th>اصلی</th><th /></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.value}-${i}`}>
                    <td className="card-title" data-label="نوع">{CHANNEL_TYPE_LABELS[r.channel_type]}</td>
                    <td data-label="برچسب">{r.label || '—'}</td>
                    <td data-label="شماره" dir="ltr">{r.value}</td>
                    <td data-label="اصلی">{r.is_primary ? 'بله' : '—'}</td>
                    <td className="card-actions">
                      <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))}>حذف</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function PeopleTab({ rows, setRows }: { rows: DraftPerson[]; setRows: Setter<DraftPerson[]> }) {
  const [draft, setDraft] = useState<DraftPerson>({
    name: '', role: '', name2: '', role2: '', phone: '', email: '', is_primary: false,
  })

  function add() {
    if (!draft.name.trim()) return
    const next = draft.is_primary ? rows.map((r) => ({ ...r, is_primary: false })) : [...rows]
    setRows([...next, { ...draft, name: draft.name.trim() }])
    setDraft({ name: '', role: '', name2: '', role2: '', phone: '', email: '', is_primary: false })
  }

  return (
    <div className="cmp-form">
      <p className="muted cmp-form-wide">
        هرکسی که به این طرف‌حساب مربوط است: برای شرکت، مدیر خرید و حسابدار؛ برای شخص،
        اعضای خانواده (پدر، همسر، فرزند) یا کسی که او را معرفی کرده.
      </p>
      <label>
        <span>نام</span>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} maxLength={200} />
      </label>
      <label>
        <span>سمت / نسبت</span>
        <input value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })}
               placeholder="مدیر خرید، پدر، معرف…" maxLength={120} />
      </label>
      <label>
        <span>نام (۲)</span>
        <input value={draft.name2} onChange={(e) => setDraft({ ...draft, name2: e.target.value })} dir="ltr" maxLength={200} />
      </label>
      <label>
        <span>سمت (۲)</span>
        <input value={draft.role2} onChange={(e) => setDraft({ ...draft, role2: e.target.value })} dir="ltr" maxLength={200} />
      </label>
      <label>
        <span>تلفن</span>
        <input value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} maxLength={30} />
      </label>
      <label>
        <span>پست الکترونیک</span>
        <input value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} maxLength={150} />
      </label>
      <label className="fy-check">
        <input type="checkbox" checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
        اصلی
      </label>
      <div className="cmp-form-wide">
        <button type="button" onClick={add} disabled={!draft.name.trim()}>افزودن شخص</button>
      </div>

      <div className="cmp-form-wide">
        {rows.length === 0 ? (
          <EmptyState icon={UserPlus} text="هنوز فردِ مرتبطی وارد نشده." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead><tr><th>نام</th><th>سمت</th><th>تلفن</th><th>پست الکترونیک</th><th>اصلی</th><th /></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={`${r.name}-${i}`}>
                    <td className="card-title" data-label="نام">{r.name}</td>
                    <td data-label="سمت">{r.role || '—'}</td>
                    <td data-label="تلفن" dir="ltr">{r.phone || '—'}</td>
                    <td data-label="پست الکترونیک" dir="ltr">{r.email || '—'}</td>
                    <td data-label="اصلی">{r.is_primary ? 'بله' : '—'}</td>
                    <td className="card-actions">
                      <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))}>حذف</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function EmployeeTab(p: {
  employeeId: string; setEmployeeId: Setter<string>
  employees: EmployeeRecord[]
  gender: string; setGender: Setter<string>
  maritalStatus: string; setMaritalStatus: Setter<string>
  maritalDate: string; setMaritalDate: Setter<string>
  childrenCount: string; setChildrenCount: Setter<string>
  dependentsCount: string; setDependentsCount: Setter<string>
  educationLevel: string; setEducationLevel: Setter<string>
  educationField: string; setEducationField: Setter<string>
}) {
  return (
    <div className="cmp-form">
      <p className="muted cmp-form-wide">
        تیکِ «کارمند» در تبِ «نقش‌ها» است. این‌جا فقط *پیوند* به رکوردِ حقوق و دستمزد
        و مشخصاتِ شخصی است — حکم، تاریخ استخدام و شماره حساب همان‌جا می‌مانند.
      </p>

      <label>
        <span>جنسیت</span>
        <SearchSelect value={p.gender} onChange={(e) => p.setGender(e.target.value)}>
          <option value="">— تعیین‌نشده —</option>
          {Object.entries(GENDER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>
      <label>
        <span>وضعیت تأهل</span>
        <SearchSelect value={p.maritalStatus} onChange={(e) => p.setMaritalStatus(e.target.value)}>
          <option value="">— تعیین‌نشده —</option>
          {Object.entries(MARITAL_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SearchSelect>
      </label>
      <label>
        <span>تاریخ وضعیت تأهل</span>
        <JalaliDatePicker value={p.maritalDate} onChange={p.setMaritalDate} />
      </label>
      <label>
        <span>تعداد فرزند</span>
        <input type="number" min="0" value={p.childrenCount} onChange={(e) => p.setChildrenCount(e.target.value)} placeholder="۰" />
      </label>
      <label>
        <span>افراد تحت تکفل</span>
        <input type="number" min="0" value={p.dependentsCount} onChange={(e) => p.setDependentsCount(e.target.value)} placeholder="۰" />
        <span className="field-hint">مبنای معافیتِ مالیاتی و بیمه — جدا از تعدادِ فرزند.</span>
      </label>
      <label>
        <span>مدرک تحصیلی</span>
        <input value={p.educationLevel} onChange={(e) => p.setEducationLevel(e.target.value)}
               placeholder="کارشناسی، دیپلم…" maxLength={50} />
      </label>
      <label>
        <span>رشته تحصیلی</span>
        <input value={p.educationField} onChange={(e) => p.setEducationField(e.target.value)} maxLength={150} />
      </label>

      {/* پیوند، نه کپی: حکم حقوقی، تاریخِ استخدام، شماره حساب، مرخصی و حضور و غیاب
          در ماژولِ حقوق و دستمزد می‌مانند. مشخصاتِ *شخصیِ* بالا این‌جاست چون واقعیتِ
          آدم است نه شغلش — مشتریِ غیرکارمند هم می‌تواند داشته باشدش. */}
      <label className="cmp-form-wide">
        <span>کارمندِ متناظر در حقوق و دستمزد</span>
        <SearchSelect value={p.employeeId} onChange={(e) => p.setEmployeeId(e.target.value)}>
          <option value="">— وصل نشده —</option>
          {p.employees.map((e) => (
            <option key={e.id} value={e.id}>{e.first_name} {e.last_name} — {e.national_id}</option>
          ))}
        </SearchSelect>
        <span className="field-hint">
          حکم حقوقی، تاریخ استخدام و شماره حساب در «حقوق و دستمزد» نگهداری می‌شوند و
          این‌جا فقط به آن وصل می‌شود — تا یک آدم دو رکوردِ ناهماهنگ نداشته باشد.
        </span>
      </label>
    </div>
  )
}
