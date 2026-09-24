import { useEffect, useState } from 'react'
import { Minus, Square, Copy, X } from 'lucide-react'
import { PRODUCT_NAME } from '../platform'

export function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false)

  useEffect(() => {
    void window.windowControls?.isMaximized().then(setIsMaximized)
    return window.windowControls?.onMaximizedChanged(setIsMaximized)
  }, [])

  return (
    <div className="titlebar">
      <div className="titlebar-drag" onDoubleClick={() => window.windowControls?.toggleMaximize()}>
        <span className="titlebar-mark">C</span>
        <span className="titlebar-title">{PRODUCT_NAME}</span>
      </div>

      <div className="titlebar-controls">
        <button
          type="button"
          className="titlebar-btn"
          onClick={() => window.windowControls?.minimize()}
          aria-label="کوچک‌کردن"
        >
          <Minus size={14} />
        </button>
        <button
          type="button"
          className="titlebar-btn"
          onClick={() => window.windowControls?.toggleMaximize()}
          aria-label={isMaximized ? 'بازگردانی' : 'بزرگ‌کردن'}
        >
          {isMaximized ? <Copy size={13} /> : <Square size={12} />}
        </button>
        <button
          type="button"
          className="titlebar-btn titlebar-btn-close"
          onClick={() => window.windowControls?.close()}
          aria-label="بستن"
        >
          <X size={15} />
        </button>
      </div>
    </div>
  )
}
