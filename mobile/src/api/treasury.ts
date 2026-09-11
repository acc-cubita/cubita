import { apiGet, apiPost } from './client'
import type { BankAccount, TreasuryTxn, TreasuryTxnIn } from './types'

// خزانه — ثبتِ دریافت/پرداخت (همان قراردادِ دسکتاپ/وب). مجوزِ سرور: checks_bank.

export const fetchBankAccounts = () => apiGet<BankAccount[]>('/api/bank-accounts')
