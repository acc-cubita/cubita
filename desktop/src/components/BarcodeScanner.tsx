import { useCallback, useEffect, useRef, useState } from 'react'
import { X, Camera, ScanLine } from 'lucide-react'

/**
 * اسکنِ بارکد با دوربینِ دستگاه — برای صندوقِ فروشگاهی و فرمِ کالا.
 *
 * از API بومیِ مرورگر (`BarcodeDetector`) استفاده می‌کند؛ هیچ کتابخانه‌ای اضافه
 * نمی‌شود. روی Chromeِ اندروید (وبِ موبایل) و Chromium/الکترون با وب‌کم کار می‌کند.
 * جایی که پشتیبانی نشود (سافاری/آی‌اواس، فایرفاکس) پیامِ روشن می‌دهد و ورودِ دستی/
 * بارکدخوانِ USB سرِ جایش می‌ماند.
 *
 * - `once`=false (پیش‌فرض، صندوق): بعد از هر اسکن باز می‌ماند تا چند کالا پشت‌سرِهم
 *   خوانده شود؛ بستن دستی است. کدِ تکراری تا ۱٫۵ ثانیه دوباره فرستاده نمی‌شود.
 * - `once`=true (فرمِ کالا): با اولین اسکنِ موفق بسته می‌شود.
 */
export function BarcodeScanner({
  onDetected,
  onClose,
  once = false,
}: {
  onDetected: (code: string) => void
  onClose: () => void
  once?: boolean
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef<number | null>(null)
  const last = useRef<{ code: string; t: number }>({ code: '', t: 0 })
  const [status, setStatus] = useState<'starting' | 'scanning' | 'error'>('starting')
  const [errText, setErrText] = useState('')
  const [lastHit, setLastHit] = useState('')

  const stop = useCallback(() => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const close = useCallback(() => {
    stop()
    onClose()
  }, [stop, onClose])

  useEffect(() => {
    let cancelled = false
    const Detector = window.BarcodeDetector

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setErrText('این مرورگر به دوربین دسترسی نمی‌دهد.')
        setStatus('error')
        return
      }
      if (!Detector) {
        setErrText(
          'اسکنِ زنده در این مرورگر پشتیبانی نمی‌شود. کد را دستی وارد کنید یا از بارکدخوانِ USB استفاده کنید. ' +
            '(روی گوشیِ اندروید با مرورگرِ Chrome کار می‌کند.)',
        )
        setStatus('error')
        return
      }

      let detector: BarcodeDetector
      try {
        detector = new Detector()
      } catch {
        setErrText('راه‌اندازیِ بارکدخوان ناموفق بود.')
        setStatus('error')
        return
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const v = videoRef.current
        if (!v) return
        v.srcObject = stream
        await v.play()
        setStatus('scanning')

        const tick = async () => {
          const v2 = videoRef.current
          if (cancelled || !v2) return
          try {
            const codes = await detector.detect(v2)
            if (codes.length) {
              const raw = codes[0].rawValue?.trim()
              const now = Date.now()
              const dup = raw === last.current.code && now - last.current.t < 1500
              if (raw && !dup) {
                last.current = { code: raw, t: now }
                setLastHit(raw)
                navigator.vibrate?.(60)
                beep()
                onDetected(raw)
                if (once) {
                  close()
                  return
                }
              }
            }
          } catch {
            /* فریمِ غیرقابل‌کشف — رد شو */
          }
          rafRef.current = requestAnimationFrame(() => void tick())
        }
        rafRef.current = requestAnimationFrame(() => void tick())
      } catch (e) {
        const name = (e as DOMException)?.name
        setErrText(
          name === 'NotAllowedError'
            ? 'اجازه‌ی دسترسی به دوربین داده نشد. از تنظیماتِ مرورگر اجازه دهید و دوباره تلاش کنید.'
            : name === 'NotFoundError'
              ? 'دوربینی پیدا نشد.'
              : 'دسترسی به دوربین ممکن نشد.',
        )
        setStatus('error')
      }
    }

    void start()
    return () => {
      cancelled = true
      stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="scanner-overlay" role="dialog" aria-modal="true" onClick={close}>
      <div className="scanner-box" onClick={(e) => e.stopPropagation()}>
        <div className="scanner-head">
          <span><ScanLine size={16} /> اسکنِ بارکد با دوربین</span>
          <button type="button" onClick={close} aria-label="بستن"><X size={18} /></button>
        </div>
        <div className="scanner-stage">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video ref={videoRef} playsInline muted />
          {status === 'scanning' && <div className="scanner-reticle" />}
          {status === 'starting' && <div className="scanner-hint">در حالِ روشن‌کردنِ دوربین…</div>}
          {status === 'scanning' && <div className="scanner-hint">بارکد را جلوی دوربین بگیرید</div>}
          {status === 'error' && (
            <div className="scanner-error">
              <Camera size={26} />
              <p>{errText}</p>
              <button type="button" className="btn-primary" onClick={close}>باشه</button>
            </div>
          )}
        </div>
        {lastHit && (
          <div className="scanner-last">آخرین اسکن: <span className="ltr-cell">{lastHit}</span></div>
        )}
      </div>
    </div>
  )
}

/** بوقِ کوتاهِ تأیید (بدونِ فایلِ صوتی — با WebAudio). */
function beep() {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = 880
    gain.gain.setValueAtTime(0.12, ctx.currentTime)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.08)
    setTimeout(() => void ctx.close(), 200)
  } catch {
    /* بی‌صدا */
  }
}
