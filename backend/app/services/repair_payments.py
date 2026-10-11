from datetime import datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4
import logging
from fastapi import HTTPException
from app import secrets_at_rest
from app.config import get_settings
from app.models.repair import RepairOnlineSettings,RepairPaymentIntent
from app.models.storefront_native import PaymentGateway
from app.models.pos_terminal import PosTerminal
from app.models.banking import BankAccount
from app.models.user import User
from app.models.receipt import Receipt
from app.schemas.receipts import ReceiptIn
from app.services import repair as core,repair_access,repair_finance as finance,receipts
from app.services.payment_providers import get_provider


def setting(db,row):
    config=db.query(RepairOnlineSettings).filter_by(branch_id=row.branch_id,enabled=True).first()
    if not config or not repair_access.available(): return None
    gateway=db.get(PaymentGateway,config.gateway_id);terminal=db.get(PosTerminal,config.pos_terminal_id)
    if not gateway or not gateway.is_active or not gateway.merchant_id or not get_provider(gateway.provider): return None
    if not terminal or not terminal.is_active or terminal.currency_code!='IRR': return None
    bank=db.get(BankAccount,terminal.bank_account_id) if terminal.bank_account_id else None
    if not bank or not bank.is_active or bank.currency_code!='IRR': return None
    return config,gateway,terminal


def configure(db,p,branch_id,data):
    core.branch(db,p,branch_id)
    # قفل شعبه حتی هنگام ساخت اولین تنظیم، رقابت upsert را کنترل می‌کند.
    from app.models.repair import RepairBranch
    db.query(RepairBranch).filter_by(id=branch_id).with_for_update().one()
    gateway=db.get(PaymentGateway,data.gateway_id);terminal=db.get(PosTerminal,data.pos_terminal_id)
    if not gateway or not terminal or terminal.currency_code!='IRR': raise HTTPException(422,'درگاه و پروفایل واقعی ریالی وجوه در راه را از همین شرکت انتخاب کنید.')
    if data.enabled and (not gateway.is_active or not gateway.merchant_id or not terminal.is_active or not get_provider(gateway.provider)):
        raise HTTPException(409,'درگاه با مرچنت و پروفایل خزانه باید فعال باشند.')
    if data.enabled and not repair_access.available(): raise HTTPException(503,'کلید حفاظت اطلاعات تنظیم نشده؛ پرداخت آنلاین فعال نمی‌شود.')
    bank=db.get(BankAccount,terminal.bank_account_id) if terminal.bank_account_id else None
    if data.enabled and (not bank or not bank.is_active or bank.currency_code!='IRR'): raise HTTPException(409,'پروفایل وجوه در راه به حساب بانکی فعال و واقعی ریالی برای تسویه نیاز دارد.')
    row=db.query(RepairOnlineSettings).filter_by(branch_id=branch_id).first()
    if row is None: row=RepairOnlineSettings(branch_id=branch_id);db.add(row)
    for k,v in data.model_dump().items(): setattr(row,k,v)
    row.configured_by_id=p.user.id;db.flush()
    return row


def public_status(db,row):
    balance=Decimal(finance.financial(db,row)['remaining_balance'])
    return {'online_payment_available':setting(db,row) is not None and balance>0,'remaining_balance_rial':str(balance),
            'payments':[{'id':p.id,'amount_rial':str(p.amount_rial),'status':p.status,'created_at':p.created_at,'verified_at':p.verified_at,'last_result':p.last_result} for p in db.query(RepairPaymentIntent).filter_by(case_id=row.id).order_by(RepairPaymentIntent.created_at.desc()).limit(100)]}


def start(db,row,token,data):
    core.check_version(row,data.version)
    configured=setting(db,row)
    if not configured: raise HTTPException(503,'درگاه واقعی، پروفایل وجوه در راه یا حفاظت مرچنت آماده نیست؛ پرداخت آغاز نشد.')
    if data.amount_rial>Decimal(finance.financial(db,row)['remaining_balance']): raise HTTPException(409,'مبلغ از ماندهٔ واقعی پرونده بیشتر است؛ مانده را تازه کنید.')
    existing=db.query(RepairPaymentIntent).filter(RepairPaymentIntent.case_id==row.id,RepairPaymentIntent.status=='pending',RepairPaymentIntent.created_at>datetime.now(timezone.utc)-timedelta(minutes=30)).first()
    if existing:
        if existing.amount_rial!=data.amount_rial: raise HTTPException(409,'درخواست پرداخت دیگری در حال انجام است؛ آن را تکمیل کنید یا پس از پایان اعتبار دوباره تلاش کنید.')
        return existing
    config,gateway,terminal=configured
    cipher=secrets_at_rest.encrypt(gateway.merchant_id)
    if not secrets_at_rest.is_encrypted(cipher): raise HTTPException(503,'حفاظت مرچنت آماده نیست؛ هیچ درخواست پرداختی ایجاد نشد.')
    intent=RepairPaymentIntent(case_id=row.id,token_id=token.id,provider=gateway.provider,merchant_ciphertext=cipher,sandbox=bool((gateway.config or {}).get('sandbox',False)),
        amount_rial=data.amount_rial,pos_terminal_id=terminal.id,posting_user_id=config.configured_by_id,authority='pending-'+str(uuid4()),redirect_url='',status='pending')
    db.add(intent);db.flush()
    callback=get_settings().app_url.rstrip('/')+f'/api/repair-payments/callback/{row.tenant_id}/{intent.id}'
    if get_settings().is_production and urlsplit(callback).scheme!='https': raise HTTPException(503,'نشانی عمومی HTTPS برای بازگشت درگاه تنظیم نشده؛ مدیر سرور باید APP_URL را بررسی کند.')
    try:
        result=get_provider(intent.provider).start(merchant_id=gateway.merchant_id,amount_rial=int(intent.amount_rial),callback_url=callback,
            description=f'تعمیرگاه؛ پذیرش {row.number}',mobile=row.owner_snapshot.get('phone',''),email='',order_ref=str(intent.id),sandbox=intent.sandbox)
    except Exception: raise HTTPException(502,'درخواست پرداخت نزد حامل تأیید نشد؛ هیچ رسیدی ثبت نشده است. دوباره تلاش کنید.')
    if not result.authority or len(result.authority)>200 or urlsplit(result.redirect_url).scheme!='https':
        raise HTTPException(502,'پاسخ معتبر پرداخت دریافت نشد؛ با تعمیرگاه تماس بگیرید.')
    intent.authority=result.authority;intent.redirect_url=result.redirect_url
    db.flush()
    return intent


def post_receipt(db,row,intent):
    if intent.receipt_id: return db.get(Receipt,intent.receipt_id)
    if intent.verified_at is None: raise HTTPException(409,'حامل پرداخت را تأیید نکرده؛ رسید مالی ثبت نمی‌شود.')
    actor=db.get(User,intent.posting_user_id)
    principal=SimpleNamespace(user=actor)
    document=receipts.create_receipt(db,ReceiptIn(contact_id=row.contact_id,receipt_date=intent.verified_at.date(),description=f'پرداخت تأییدشدهٔ درگاه؛ پذیرش {row.number}',
        cards=[{'pos_terminal_id':intent.pos_terminal_id,'reference_no':intent.provider+':'+intent.payment_ref,'amount':intent.amount_rial}]),actor)
    finance.link(db,principal,row,'receipt',document,snapshot={'payment_intent_id':str(intent.id),'provider':intent.provider})
    finance.allocate(db,principal,row,intent.verified_at.date())
    intent.receipt_id=document.id;intent.status='posted';intent.last_result='تأیید حامل و ثبت رسید واقعی در وجوه در راه انجام شد.'
    if row.status=='closed' and Decimal(finance.financial(db,row)['remaining_balance'])!=0: row.status='delivered'
    core.event(db,principal,row,'online_payment_posted',{'payment_intent_id':str(intent.id),'receipt_id':str(document.id),'provider':intent.provider})
    return document


def verify(db,row,intent,params):
    provider=get_provider(intent.provider)
    if not provider: intent.last_result='آداپتور درگاه در دسترس نیست؛ رسید ثبت نشده.';return False
    callback=provider.parse_callback(params)
    if callback.authority!=intent.authority: raise HTTPException(400,'شناسهٔ بازگشت درگاه با درخواست ثبت‌شده برابر نیست.')
    if intent.status=='posted': return True
    if intent.verified_at is None:
        if not callback.ok_signal: intent.last_result='بازگشت حامل موفقیت را نشان نداد؛ رسید ثبت نشد.';return False
        try:
            merchant=secrets_at_rest.decrypt(intent.merchant_ciphertext)
            ok,ref=provider.verify(merchant_id=merchant,amount_rial=int(intent.amount_rial),authority=intent.authority,order_ref=str(intent.id),sandbox=intent.sandbox)
        except Exception:
            intent.last_result='تأیید سرور درگاه در دسترس نبود؛ دریافت وجه هنوز تأیید نشده است.';return False
        if not ok or not ref:
            intent.status='verification_failed';intent.last_result='سرور درگاه پرداخت را تأیید نکرد؛ هیچ رسیدی ثبت نشد.';return False
        intent.verified_at=datetime.now(timezone.utc);intent.payment_ref=str(ref)[:200];intent.status='accounting_pending'
        db.flush()
    try:
        with db.begin_nested(): post_receipt(db,row,intent)
    except Exception as exc:
        # اثبات پرداخت از خطای تنظیم حساب مستقل است و از دست نمی‌رود.
        intent.status='accounting_pending';intent.last_result='حامل پرداخت را تأیید کرده؛ ثبت رسید به بررسی مدیر خزانه نیاز دارد.'
        logging.getLogger('cubita.repair_payment').error('ثبت رسید پرداخت تأییدشده نیازمند بررسی است؛ نوع خطا: %s',type(exc).__name__)
        db.flush()
        return False
    return True
