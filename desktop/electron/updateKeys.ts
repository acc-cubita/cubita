// کلیدهای عمومیِ امضای آپدیتِ «کوبیتا سازمانی» — **باید عیناً همان `TRUSTED_PUBLIC_KEYS`ِ
// `backend/app/licensing/keys.py` باشد** (یک کلید مجوز و آپدیت را امضا می‌کند، با پیشوندِ
// زمینه‌ی جدا). تستِ `backend/tests/test_enterprise_updates.py::test_client_and_server_keys_match`
// ناهمخوانیِ این دو را می‌گیرد.
//
// خالی = هیچ آپدیتی نصب نمی‌شود (fail-closed)، تا وقتی کلیدِ تولید ساخته شود
// (دستور در ENTERPRISE_PLAN.md، «نتایجِ M2»).

//: kid → کلیدِ عمومیِ خامِ Ed25519 به base64url.
export const TRUSTED_UPDATE_KEYS: Record<string, string> = {}
