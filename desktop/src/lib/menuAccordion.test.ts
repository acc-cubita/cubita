import { beforeEach, describe, expect, it } from 'vitest'

import { openCategory, resetOpenCategories, toggleCategory } from './menuAccordion'

beforeEach(resetOpenCategories)

describe('آکاردئونِ دسته‌های منو', () => {
  it('پیش‌فرض همه بسته‌اند', () => {
    expect(openCategory('حسابداری')).toBeNull()
  })

  it('باز کردنِ یک دسته دسته‌ی بازِ قبلی را می‌بندد؛ ضربه‌ی دوباره می‌بندد', () => {
    expect(toggleCategory('حسابداری', 'ثبت سند')).toBe('ثبت سند')
    expect(toggleCategory('حسابداری', 'پایان دوره')).toBe('پایان دوره')
    expect(openCategory('حسابداری')).toBe('پایان دوره')
    expect(toggleCategory('حسابداری', 'پایان دوره')).toBeNull()
  })

  it('هر ماژول دسته‌ی بازِ خودش را دارد', () => {
    toggleCategory('حسابداری', 'ثبت سند')
    toggleCategory('مشتریان و فروش', 'کار روزانه')
    expect(openCategory('حسابداری')).toBe('ثبت سند')
    expect(openCategory('مشتریان و فروش')).toBe('کار روزانه')
  })
})
