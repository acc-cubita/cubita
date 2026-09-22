import { getLocalDb } from './db.js'

// نشستِ ورودِ آفلاین: بارِ اول کاربر یوزر/پسورد می‌زند، از آن به بعد اپ خودش
// وارد می‌ماند — با رفرش‌توکنِ ۶۰روزه‌ی چرخشی‌ای که سرور از قبل برای «همیشه‌
// واردمانده»ی موبایل صادر می‌کرد (services/refresh.py) و دسکتاپ تا امروز
// دورش می‌ریخت. رمزِ خام هرگز ذخیره نمی‌شود؛ فقط همین توکن.
//
// **قاعده‌ی طلایی:** خطای شبکه هرگز نشست را باطل نمی‌کند. فقط ۴۰۱ِ صریحِ سرور
// (رفرش باطل/منقضی/رمز عوض‌شده) این کار را می‌کند. بدونِ این تفکیک — که باگِ
// اصلیِ نسخه‌ی قبل بود — یک قطعیِ کوتاهِ اینترنت هم مثلِ خروجِ واقعی رفتار
// می‌کرد و کاربر را به صفحه‌ی ورود پرت می‌کرد، دقیقاً همان‌جا که بدونِ اینترنت
// نمی‌تواند از آن رد شود.

interface SessionConfig {
  apiBaseUrl: string
}

export interface StoredSession {
  access_token: string
  refresh_token: string
  me: unknown
}

export type RestoreResult = { session: StoredSession; offline: boolean } | null

interface SessionRow {
  access_token: string
  refresh_token: string
  me_json: string
}

function readRow(): StoredSession | null {
  const row = getLocalDb().prepare('SELECT access_token, refresh_token, me_json FROM session WHERE id = 1').get() as
    | SessionRow
    | undefined
  if (!row) return null
  try {
    return { access_token: row.access_token, refresh_token: row.refresh_token, me: JSON.parse(row.me_json) }
  } catch {
    // me_json خراب — نشستِ نیمه‌سالم بدتر از هیچ‌چیز است، پاکش می‌کنیم.
    clearSession()
    return null
  }
}

/** بعد از ورود/ثبت‌نام/تعیینِ رمز/سوییچِ کسب‌وکار صدا زده می‌شود — نشستِ کامل. */
export function persistSession(access: string, refresh: string, me: unknown): void {
  getLocalDb()
    .prepare(
      `INSERT INTO session (id, access_token, refresh_token, me_json, updated_at)
       VALUES (1, @access_token, @refresh_token, @me_json, datetime('now'))
       ON CONFLICT(id) DO UPDATE SET
         access_token = excluded.access_token,
         refresh_token = excluded.refresh_token,
         me_json = excluded.me_json,
         updated_at = excluded.updated_at`,
    )
    .run({ access_token: access, refresh_token: refresh, me_json: JSON.stringify(me) })
}

/** فقط توکن‌ها را به‌روز می‌کند — بعد از رفرشِ خاموشِ موفق، پیش از فراخوانِ /me. */
function writeTokens(access: string, refresh: string): void {
  getLocalDb()
    .prepare(`UPDATE session SET access_token = @a, refresh_token = @r, updated_at = datetime('now') WHERE id = 1`)
    .run({ a: access, r: refresh })
}

export function clearSession(): void {
  getLocalDb().prepare('DELETE FROM session WHERE id = 1').run()
}

/** رفرشِ فعلی — برای خروجِ سمتِ سرور (بهترین‌تلاش)، بدونِ نیاز به بازخواندنِ کل نشست. */
export function currentRefreshToken(): string | null {
  const row = getLocalDb().prepare('SELECT refresh_token FROM session WHERE id = 1').get() as
    | { refresh_token: string }
    | undefined
  return row?.refresh_token ?? null
}

type RefreshAttempt =
  | { ok: true; access: string; refresh: string }
  | { ok: false; reason: 'network' | 'invalid' }

async function tryRefresh(apiBaseUrl: string, refreshToken: string): Promise<RefreshAttempt> {
  let res: Response
  try {
    res = await fetch(`${apiBaseUrl}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  } catch {
    // fetch خودش throw می‌کند یعنی درخواست اصلاً به سرور نرسید — قطعیِ شبکه،
    // نه بطلانِ نشست. رفرشِ قدیمی روی سرور دست‌نخورده مانده (هرگز نرسید که
    // چرخانده شود)، پس چیزی برای هماهنگ‌کردن نیست.
    return { ok: false, reason: 'network' }
  }
  // فقط ۴۰۱ِ صریح یعنی رفرش واقعاً مرده (باطل/منقضی/نسلِ رمز عوض‌شده). هر
  // خطای دیگرِ سرور (۵۰۰ و مشابه) هم مثلِ قطعیِ شبکه رفتار می‌کند — یک هیچِ
  // گذرای سرور نباید کاربر را از نشستِ معتبرش بیرون بیندازد.
  if (res.status === 401) return { ok: false, reason: 'invalid' }
  if (!res.ok) return { ok: false, reason: 'network' }

  const body = (await res.json().catch(() => null)) as { access_token?: string; refresh_token?: string } | null
  if (!body?.access_token || !body.refresh_token) return { ok: false, reason: 'network' }
  return { ok: true, access: body.access_token, refresh: body.refresh_token }
}

async function fetchMe(apiBaseUrl: string, access: string): Promise<unknown | null> {
  try {
    const res = await fetch(`${apiBaseUrl}/api/auth/me`, { headers: { Authorization: `Bearer ${access}` } })
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

/**
 * بازیابیِ نشست در بدو اجرا. سه خروجی:
 *
 * - `null` — نشستی ذخیره نشده، یا رفرش با ۴۰۱ِ صریح رد شد (نشست پاک شد). تنها
 *   حالتی که باید صفحه‌ی ورود نشان داده شود.
 * - `{offline:false}` — آنلاین: رفرش و /me هر دو موفق، توکن‌های تازه‌ی چرخشی
 *   ذخیره شدند.
 * - `{offline:true}` — قطعیِ شبکه (یا خطای گذرای سرور) در رفرش یا /me. همان
 *   نشستِ ذخیره‌شده (یا توکنِ تازه‌ای که تا همین‌جا گرفته شد) برمی‌گردد؛ هیچ‌چیز
 *   پاک نمی‌شود.
 */
export async function restoreSession(config: SessionConfig): Promise<RestoreResult> {
  const stored = readRow()
  if (!stored) return null

  const attempt = await tryRefresh(config.apiBaseUrl, stored.refresh_token)
  if (!attempt.ok) {
    if (attempt.reason === 'invalid') {
      clearSession()
      return null
    }
    return { session: stored, offline: true }
  }

  // رفرشِ چرخشی همین‌جا روی سرور مصرف شده — قبل از تلاشِ /me ذخیره می‌شود، وگرنه
  // قطعیِ شبکه‌ی درست‌بعد از این نقطه، توکنِ محلی را با رفرشِ مرده جا می‌گذاشت.
  writeTokens(attempt.access, attempt.refresh)

  const me = await fetchMe(config.apiBaseUrl, attempt.access)
  if (me === null) {
    return {
      session: { access_token: attempt.access, refresh_token: attempt.refresh, me: stored.me },
      offline: true,
    }
  }

  getLocalDb().prepare(`UPDATE session SET me_json = @m WHERE id = 1`).run({ m: JSON.stringify(me) })
  return { session: { access_token: attempt.access, refresh_token: attempt.refresh, me }, offline: false }
}

/** خروجِ سمتِ سرور — بهترین‌تلاش. شکست (آفلاین بودن، رفرشِ ازقبل‌مرده) خروجِ محلی را متوقف نمی‌کند. */
export async function bestEffortLogout(config: SessionConfig): Promise<void> {
  const refresh = currentRefreshToken()
  if (!refresh) return
  try {
    await fetch(`${config.apiBaseUrl}/api/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
  } catch {
    // آفلاین یا هر خطای دیگر — خروجِ محلی مستقل از این ادامه دارد.
  }
}
