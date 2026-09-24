// وقتی همین اپ در مرورگر (بدون Electron) اجرا می‌شود، window.cubita اصلاً تزریق نمی‌شود؛ برای تشخیص همین کافی است.
export const isElectron = typeof window !== 'undefined' && !!window.cubita

// «کوبیتا سازمانی» — نسخه را main فریز کرده و preload داده؛ در وب همیشه ابری است.
export const isEnterprise = typeof window !== 'undefined' && window.cubitaConfig?.edition === 'enterprise'

// سازمانی‌ای که هنوز به سرورِ شرکت وصل نشده — جادوگرِ «اتصال به سرور» باید باز شود.
export const needsServerAddress = isEnterprise && !window.cubitaConfig?.serverUrl

// نامِ محصول در نوارِ عنوان و سرِ منو — دو محصولِ جدا، دو نام.
export const PRODUCT_NAME = isEnterprise ? 'کوبیتا سازمانی' : 'کوبیتا'
