import { outboxErrorText } from './outboxError'

export const REFERENCE_SOURCES = {
  accounts: { label: 'چارت حساب‌ها', permission: 'accounting' },
  warehouses: { label: 'انبارها', permission: 'inventory' },
  items: { label: 'کالاها', permission: 'inventory' },
  bankAccounts: { label: 'حساب‌های بانکی', permission: 'checks_bank' },
} as const

export type ReferenceKey = keyof typeof REFERENCE_SOURCES
export type SyncPermissions = Record<string, string[]>
export interface ReferenceSyncReport {
  pulled: ReferenceKey[]
  skipped: ReferenceKey[]
  failed: { key: ReferenceKey; message: string }[]
}
export interface ReferencePull {
  key: ReferenceKey
  run: () => Promise<void>
  onSkipped?: () => void | Promise<void>
}

export function referenceAllowed(permissions: SyncPermissions | undefined, key: ReferenceKey): boolean {
  // فراخواننده‌های قدیمی بدونِ نقشه هنوز از گاردِ واقعیِ سرور استفاده می‌کنند.
  if (!permissions) return true
  return [REFERENCE_SOURCES[key].permission, '*'].some((module) =>
    permissions[module]?.some((action) => action === 'view' || action === '*'),
  )
}

/** ردشدنِ انبار نباید حساب‌های موفق را از دسترسِ حسابدار بیرون ببرد؛ هر بخش نتیجهٔ مستقل دارد. */
export async function runReferenceSync(tasks: ReferencePull[], permissions?: SyncPermissions): Promise<ReferenceSyncReport> {
  const report: ReferenceSyncReport = { pulled: [], skipped: [], failed: [] }
  const results = await Promise.all(tasks.map(async (task) => {
    try {
      if (!referenceAllowed(permissions, task.key)) {
        await task.onSkipped?.()
        return { key: task.key, state: 'skipped' as const }
      }
      try {
        await task.run()
      } catch (error) {
        // نقشهٔ مجوز فقط برای کم‌کردن درخواست است؛ اگر کهنه باشد، ۴۰۳ِ سرور مرجع می‌ماند.
        if (!error || typeof error !== 'object' || !('status' in error) || error.status !== 403) throw error
        await task.onSkipped?.()
        return { key: task.key, state: 'skipped' as const }
      }
      return { key: task.key, state: 'pulled' as const }
    } catch (error) {
      return { key: task.key, state: 'failed' as const, message: outboxErrorText(error instanceof Error ? error.message : String(error)) }
    }
  }))
  for (const result of results) {
    if (result.state === 'failed') report.failed.push({ key: result.key, message: result.message })
    else report[result.state].push(result.key)
  }
  return report
}

export function referenceSyncMessage(report: ReferenceSyncReport, outbox?: { pushed: number; failed: number }): string {
  const parts = [report.failed.length
    ? (report.pulled.length ? 'هم‌گام‌سازی بخشی انجام شد' : 'دریافت اطلاعات انجام نشد')
    : 'هم‌گام‌سازی بخش‌های مجاز کامل شد']
  if (outbox) parts.push(`ارسال‌شده: ${outbox.pushed.toLocaleString('fa-IR')}، ناموفق: ${outbox.failed.toLocaleString('fa-IR')}`)
  if (report.skipped.length) parts.push(`بدون دسترسی: ${report.skipped.map((key) => REFERENCE_SOURCES[key].label).join('، ')}`)
  for (const failure of report.failed) parts.push(`${REFERENCE_SOURCES[failure.key].label}: ${failure.message}`)
  if (outbox?.failed) parts.push('سندهای ناموفق در صف حفظ شده‌اند؛ علت را در صف همان بخش ببینید و دوباره ثبتشان نکنید.')
  return parts.join(' — ')
}
