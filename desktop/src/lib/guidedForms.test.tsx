// @vitest-environment jsdom
/**
 * ویزارد یا فرمِ فشرده — با **حالت**، نه با تم (UI-01 §۳۲).
 *
 * تا این تغییر نُه فرم با `theme.content === 'guided'` تصمیم می‌گرفتند. هر سه تم
 * «مرحله‌ای»اند، پس فرم‌های کلاسیک از هیچ‌جا باز نمی‌شدند و هیچ خطایی هم این را
 * نمی‌گفت. این فایل دو چیز را نگه می‌دارد: هوک با حالت همان لحظه عوض می‌شود و با
 * تم اصلاً عوض نمی‌شود، و هیچ فرمی دوباره سراغِ تم نمی‌رود.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { __resetExperienceForTests, setExperience, useGuidedForms } from './experienceMode'
import { THEMES, applyTheme } from './theme'

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root.render(createElement(() => (useGuidedForms() ? 'wizard' : 'classic')))
  })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('انتخابِ فرم', () => {
  it('حسابدار فرمِ فشرده می‌گیرد، ساده ویزارد — و همان لحظه‌ی عوض‌شدنِ حالت', () => {
    expect(container.textContent).toBe('classic')
    act(() => setExperience('simple'))
    expect(container.textContent).toBe('wizard')
    act(() => setExperience('accountant'))
    expect(container.textContent).toBe('classic')
  })

  it('**حالت ≠ تم** — هیچ تمی انتخابِ فرم را عوض نمی‌کند', () => {
    for (const t of THEMES) {
      act(() => applyTheme(t.id))
      expect(container.textContent, t.id).toBe('classic')
    }
  })
})

describe('هیچ فرمی دوباره با تم تصمیم نمی‌گیرد', () => {
  //: `import.meta.glob`ِ خودِ Vite، نه `node:fs`: tsconfigِ اپ فقط تایپ‌های `vite/client`
  //: را دارد. کلیدها نسبت به همین پوشه‌اند (`../components/Dashboard.tsx`).
  const sources = import.meta.glob(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}'], {
    query: '?raw',
    import: 'default',
    eager: true,
  }) as Record<string, string>

  it('`content === \'guided\'` فقط در داشبوردِ overview می‌ماند', () => {
    //: داشبورد صفحه است نه فرم، و کارت‌هایش از #173 با حالت عوض می‌شوند؛ پس
    //: عمداً روی تم ماند. هر جای دیگری که این شرط برگردد، یعنی فرمی دوباره
    //: فرمِ کلاسیک را از حسابدار پنهان کرده.
    expect(Object.keys(sources).length).toBeGreaterThan(100) // الگو واقعاً فایل‌ها را گرفته
    const hits = Object.entries(sources).flatMap(([f, text]) => {
      const n = (text.match(/content\s*===\s*['"]guided['"]/g) ?? []).length
      return n ? [`${f.replace(/^\.\.\//, '')}×${n}`] : []
    })
    expect(hits).toEqual(['components/Dashboard.tsx×1'])
  })
})
