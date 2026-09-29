import type { ServerConnection } from '../src/lib/serverConnection.js'

interface Dependencies {
  url: () => string | null
  probe: (url: string) => Promise<{ ok: boolean }>
  local: (url: string) => boolean
  recover: () => Promise<Pick<ServerConnection, 'state' | 'message'>>
  emit: (status: ServerConnection) => void
  now?: () => number
}

/** No session/cache/network writes here. Failed connections retry the SAME origin. */
export class ServerConnectionMonitor {
  private status: ServerConnection = { state: 'checking', message: 'در حال بررسی اتصال به سرور…', url: null }
  private flight: Promise<ServerConnection> | null = null
  private checkedAt = -Infinity
  private recoveryAt = -Infinity
  private timer: ReturnType<typeof setInterval> | null = null
  private readonly now: () => number
  private readonly dep: Dependencies
  constructor(dep: Dependencies) { this.dep = dep; this.now = dep.now ?? Date.now }

  snapshot(): ServerConnection { return { ...this.status } }

  start(): void {
    if (this.timer) return
    void this.check()
    this.timer = setInterval(() => { void this.check() }, 10_000)
    this.timer.unref?.()
  }

  stop(): void { if (this.timer) clearInterval(this.timer); this.timer = null }

  private publish(next: ServerConnection): void {
    if (next.url !== this.dep.url()) return // result from an old, explicitly changed server
    const changed = JSON.stringify(next) !== JSON.stringify(this.status)
    this.status = next
    if (changed) this.dep.emit(this.snapshot())
  }

  check(force = false): Promise<ServerConnection> {
    if (this.flight) return this.flight
    if (!force && this.now() - this.checkedAt < 3000) return Promise.resolve(this.snapshot())
    this.checkedAt = this.now()
    const url = this.dep.url()
    this.flight = this.run(url).catch(() => {
      this.publish({ state: 'offline', url, message: 'سرور هنوز پاسخ نمی‌دهد؛ اتصال خودکار دوباره بررسی می‌شود. داده‌ها و صف محفوظ‌اند.' })
      return this.snapshot()
    }).finally(() => { this.flight = null })
    return this.flight
  }

  private async run(url: string | null): Promise<ServerConnection> {
    if (!url) {
      this.publish({ state: 'unconfigured', url, message: 'نشانی سرور را فقط بار اول انتخاب و ذخیره کنید.' })
      return this.snapshot()
    }
    const healthy = await this.dep.probe(url).catch(() => ({ ok: false }))
    if (url !== this.dep.url()) return this.snapshot()
    if (healthy.ok) {
      this.publish({ state: 'ready', url, message: 'ارتباط با سرور برقرار است.' })
    } else if (this.dep.local(url) && this.now() - this.recoveryAt >= 60_000) {
      this.recoveryAt = this.now()
      this.publish({ state: 'starting', url, message: 'در حال راه‌اندازی خودکار سرور؛ لطفاً کمی صبر کنید…' })
      const result = await this.dep.recover()
      if (url !== this.dep.url()) return this.snapshot()
      // A running SCM wrapper isn't proof that the configured API answers.
      if (result.state === 'ready' && (await this.dep.probe(url)).ok) {
        this.publish({ state: 'ready', url, message: 'سرور راه‌اندازی شد؛ اتصال خودکار برقرار است.' })
      } else if (result.state !== 'ready' && result.state !== 'client') {
        this.publish({ ...result, url })
      } else {
        this.publish({ state: 'offline', url, message: 'سرور هنوز پاسخ نمی‌دهد؛ اتصال خودکار دوباره بررسی می‌شود. داده‌ها و صف محفوظ‌اند.' })
      }
    } else if (this.status.url !== url || !['maintenance', 'permission', 'missing', 'repair'].includes(this.status.state)) {
      this.publish({ state: 'offline', url, message: 'ارتباط با سرور قطع است؛ برنامه به همین سرور دوباره وصل می‌شود. رایانهٔ سرور باید روشن باشد.' })
    }
    return this.snapshot()
  }
}
