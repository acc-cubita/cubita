export function LightStreakBackground() {
  return (
    <div className="streak-bg" aria-hidden="true">
      <svg viewBox="0 0 1600 1200" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="streakA" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0" />
            <stop offset="35%" stopColor="#3b82f6" stopOpacity="0.9" />
            <stop offset="65%" stopColor="#8b5cf6" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="streakB" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0" />
            <stop offset="40%" stopColor="#ec4899" stopOpacity="0.85" />
            <stop offset="70%" stopColor="#8b5cf6" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="streakC" x1="10%" y1="100%" x2="90%" y2="10%">
            <stop offset="0%" stopColor="#60a5fa" stopOpacity="0" />
            <stop offset="50%" stopColor="#60a5fa" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#c084fc" stopOpacity="0" />
          </linearGradient>
          <filter id="streakBlur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="34" />
          </filter>
          <filter id="streakBlurSoft" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="60" />
          </filter>
        </defs>

        <g filter="url(#streakBlurSoft)" opacity="0.55">
          <path d="M -100 950 C 250 800, 480 1000, 750 780 S 1250 400, 1750 250" stroke="url(#streakA)" strokeWidth="90" fill="none" strokeLinecap="round" />
        </g>

        <g filter="url(#streakBlur)" opacity="0.85">
          <path d="M -150 700 C 200 620, 420 800, 700 600 S 1150 280, 1700 120" stroke="url(#streakA)" strokeWidth="46" fill="none" strokeLinecap="round" />
          <path d="M -150 1050 C 300 980, 600 1120, 900 900 S 1400 560, 1750 480" stroke="url(#streakB)" strokeWidth="38" fill="none" strokeLinecap="round" />
          <path d="M 100 1250 C 420 1080, 650 1180, 950 950 S 1500 500, 1800 380" stroke="url(#streakC)" strokeWidth="26" fill="none" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  )
}
