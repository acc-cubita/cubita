import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MessageSquare, X, Send, Loader2, AlertCircle } from 'lucide-react'
import { fetchMpMessages, sendMpMessage, type MpMessage } from '../api'

const POLL_MS = 4000

const faTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

/**
 * کشوی گفتگوی یک اتصالِ بازار (فروشگاه↔پخش‌کننده) — یک رشته‌ی متنیِ دائم به‌ازای هر اتصالِ
 * approved. تحویلِ زنده با **پول‌کردن** هر چند ثانیه است (نه WebSocket)؛ باز/پول‌کردنِ رشته
 * روی سرور آن را «خوانده» می‌کند، پس `onSeen` به والد می‌گوید نشانِ خوانده‌نشده را نو کند.
 * فقط آنلاین کار می‌کند (چت ذاتاً برخط است).
 */
export function MarketplaceChatDrawer({
  token,
  connectionId,
  partnerName,
  onClose,
  onSeen,
}: {
  token: string
  connectionId: string
  partnerName: string
  onClose: () => void
  onSeen?: () => void
}) {
  const [messages, setMessages] = useState<MpMessage[]>([])
  const [myRole, setMyRole] = useState<'distributor' | 'retailer' | null>(null)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const lastTs = useRef<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const onSeenRef = useRef(onSeen)
  onSeenRef.current = onSeen

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const el = listRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
  }, [])

  // بارگیریِ اولیه‌ی کلِ رشته، سپس پولِ افزایشی (فقط پیام‌های بعد از آخرین).
  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    const schedule = () => {
      timer = window.setTimeout(() => void poll(), POLL_MS)
    }

    const poll = async () => {
      try {
        const page = await fetchMpMessages(token, connectionId, lastTs.current ?? undefined)
        if (cancelled) return
        setError(null)
        if (page.messages.length) {
          lastTs.current = page.messages[page.messages.length - 1].created_at
          setMessages((prev) => [...prev, ...page.messages])
          scrollToBottom()
        }
        onSeenRef.current?.()
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'خطا در دریافتِ پیام‌ها')
      } finally {
        if (!cancelled) schedule()
      }
    }

    fetchMpMessages(token, connectionId)
      .then((page) => {
        if (cancelled) return
        setMyRole(page.my_role)
        setMessages(page.messages)
        lastTs.current = page.messages.length ? page.messages[page.messages.length - 1].created_at : null
        setLoading(false)
        scrollToBottom()
        onSeenRef.current?.()
        schedule()
      })
      .catch((e) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'خطا در دریافتِ پیام‌ها')
        setLoading(false)
        schedule()
      })

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [token, connectionId, scrollToBottom])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const send = useCallback(async () => {
    const body = input.trim()
    if (!body || sending) return
    setSending(true)
    setError(null)
    try {
      const msg = await sendMpMessage(token, connectionId, body)
      setMessages((prev) => [...prev, msg])
      lastTs.current = msg.created_at
      setInput('')
      scrollToBottom()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'ارسال ناموفق بود')
    } finally {
      setSending(false)
    }
  }, [input, sending, token, connectionId, scrollToBottom])

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer-panel mp-chat-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="drawer-head">
          <div className="drawer-title">
            <MessageSquare size={17} />
            <div>
              <div className="drawer-title-main">گفتگو: {partnerName}</div>
              <div className="drawer-title-sub">پیام‌های بین شما و طرفِ مقابل</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن">
            <X size={18} />
          </button>
        </div>

        <div className="mp-chat-body" ref={listRef}>
          {loading ? (
            <div className="mp-chat-empty">
              <Loader2 className="spin" size={20} /> در حالِ بارگیری…
            </div>
          ) : messages.length === 0 ? (
            <div className="mp-chat-empty">
              <MessageSquare size={24} />
              هنوز پیامی نیست. اولین پیام را بفرستید.
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={`mp-chat-msg ${m.sender_role === myRole ? 'mine' : 'theirs'}`}>
                <div className="mp-chat-bubble">{m.body}</div>
                <div className="mp-chat-time">{faTime(m.created_at)}</div>
              </div>
            ))
          )}
        </div>

        {error && (
          <div className="mp-chat-error">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        <form
          className="mp-chat-composer"
          onSubmit={(e) => {
            e.preventDefault()
            void send()
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void send()
              }
            }}
            placeholder="پیام بنویسید… (Enter برای ارسال، Shift+Enter خطِ تازه)"
            rows={1}
          />
          <button
            type="submit"
            className="btn-primary mp-chat-send"
            disabled={sending || !input.trim()}
            aria-label="ارسال"
          >
            {sending ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
          </button>
        </form>
      </div>
    </div>,
    document.body,
  )
}
