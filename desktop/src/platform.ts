// وقتی همین اپ در مرورگر (بدون Electron) اجرا می‌شود، window.cubita اصلاً تزریق نمی‌شود؛ برای تشخیص همین کافی است.
export const isElectron = typeof window !== 'undefined' && !!window.cubita
