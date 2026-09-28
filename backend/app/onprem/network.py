"""تنظیم محلی شبکه؛ مستقل از دفتر مالی و API، با گارد دوباره در هر راه‌اندازی.

IP فقط روی کارت فیزیکیِ سیمیِ جدا از اینترنت اضافه می‌شود. DHCPِ شبکهٔ مشترک،
DNS، gateway، route، metric، VPN و دسته‌بندی عمومی/خصوصی هرگز تغییر نمی‌کنند.
"""

from __future__ import annotations

import ipaddress
import uuid

TOPOLOGIES = {"direct", "wired-router", "wifi-router", "mixed", "other"}
PRIVATE = tuple(ipaddress.IPv4Network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class NetworkError(ValueError):
    pass


def private_address(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError) as exc:
        raise NetworkError("IP معتبرِ شبکهٔ داخلی را وارد کنید؛ مانند 192.168.50.1.") from exc
    if not any(address in net for net in PRIVATE):
        raise NetworkError("فقط IP خصوصیِ شبکهٔ داخلی مجاز است؛ IP عمومی، loopback و VPN را انتخاب نکنید.")
    return address


def network_of(address: str, prefix: int) -> ipaddress.IPv4Network:
    if type(prefix) is not int or not 16 <= prefix <= 30:
        raise NetworkError("طول پیشوند باید بین ۱۶ و ۳۰ باشد؛ برای دو رایانه معمولاً ۲۴ است.")
    ip = private_address(address)
    net = ipaddress.IPv4Network((ip, prefix), strict=False)
    if not any(net.subnet_of(n) for n in PRIVATE) or ip in (net.network_address, net.broadcast_address):
        raise NetworkError("IP نباید نشانیِ خود شبکه یا broadcast باشد؛ IP میزبان و پیشوند را اصلاح کنید.")
    return net


def validate_config(raw: dict) -> dict:
    allowed = {"adapterId", "topology", "mode", "address", "prefix", "port", "startup", "staticConsent"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise NetworkError("تنظیم شبکه نامعتبر است؛ فرم را دوباره باز کنید.")
    try:
        adapter_id = str(uuid.UUID(str(raw.get("adapterId", "")).strip("{}")))
    except ValueError as exc:
        raise NetworkError("کارت شبکه را از فهرست همین رایانه انتخاب کنید.") from exc
    topology, mode = raw.get("topology"), raw.get("mode")
    if not isinstance(topology, str) or not isinstance(mode, str) or topology not in TOPOLOGIES or mode not in {"keep", "static"}:
        raise NetworkError("نوع ارتباط و حالت تنظیم IP را انتخاب کنید.")
    if type(raw.get("port")) is not int or not 1024 <= raw["port"] <= 65535:
        raise NetworkError("پورت سرور باید عددی بین ۱۰۲۴ و ۶۵۵۳۵ باشد.")
    for flag in ("startup", "staticConsent"):
        if type(raw.get(flag, False)) is not bool:
            raise NetworkError("گزینهٔ تأییدِ شبکه نامعتبر است.")
    address = str(raw.get("address", ""))
    net = network_of(address, raw.get("prefix"))
    if mode == "static" and (topology != "direct" or not raw.get("staticConsent")):
        raise NetworkError("IP ثابت فقط برای کابل مستقیمِ جدا از اینترنت و با تأیید صریح مجاز است.")
    return {
        "adapterId": adapter_id, "topology": topology, "mode": mode,
        "address": str(private_address(address)), "prefix": net.prefixlen,
        "port": raw["port"], "startup": raw.get("startup", False),
        "staticConsent": raw.get("staticConsent", False),
    }


def adapter_for(config: dict, inventory: dict) -> dict:
    adapter = next((a for a in inventory["adapters"] if a["id"].lower() == config["adapterId"].lower()), None)
    if not adapter or not adapter["physical"] or adapter["kind"] not in {"wired", "wifi"}:
        raise NetworkError("کارت فیزیکیِ انتخاب‌شده پیدا نشد؛ کارت مجازی/VPN مجاز نیست. فهرست را تازه کنید.")
    if adapter["status"] != "Up":
        raise NetworkError("کارت شبکه وصل نیست؛ کابل یا Wi‑Fi را وصل کنید و دوباره بررسی کنید.")
    if config["topology"] in {"direct", "wired-router"} and adapter["kind"] != "wired":
        raise NetworkError("برای ارتباط سیمی باید کارت LAN فیزیکی انتخاب شود.")
    if config["topology"] == "wifi-router" and adapter["kind"] != "wifi":
        raise NetworkError("برای ارتباط Wi‑Fi باید کارت بی‌سیم فیزیکی انتخاب شود.")
    return adapter


def _overlaps(net: ipaddress.IPv4Network, other: dict) -> bool:
    for item in other.get("addresses", []):
        try:
            if net.overlaps(ipaddress.IPv4Network(f'{item["address"]}/{item["prefix"]}', strict=False)):
                return True
        except ValueError:
            continue
    return False


def isolated_guard(adapter: dict, inventory: dict, net: ipaddress.IPv4Network) -> None:
    if adapter["kind"] != "wired" or adapter.get("gateways") or adapter.get("defaultRoute"):
        raise NetworkError("این کارت مسیر اینترنت یا gateway دارد؛ IP/DHCP تغییر نمی‌کند. حالت «حفظ تنظیمات فعلی» را انتخاب کنید.")
    for other in inventory["adapters"]:
        if other["id"] != adapter["id"] and _overlaps(net, other):
            raise NetworkError("این محدوده با کارت دیگری (از جمله Wi‑Fi یا VPN) تداخل دارد؛ محدودهٔ دیگری انتخاب کنید.")
    for route in inventory.get("routes", []):
        # VPNها گاهی دو /1 به‌جای default می‌سازند؛ این مسیرها نباید از LAN تازه ربوده شوند.
        try:
            r = ipaddress.IPv4Network(route["destination"], strict=False)
        except ValueError:
            continue
        if route["index"] != adapter["index"] and r.prefixlen != 0 and r.overlaps(net):
            raise NetworkError("محدودهٔ انتخاب‌شده با مسیرِ شبکه/VPN تداخل دارد؛ ابتدا محدودهٔ دیگری انتخاب کنید.")


def make_plan(raw: dict, inventory: dict) -> dict:
    config = validate_config(raw)
    adapter = adapter_for(config, inventory)
    net = network_of(config["address"], config["prefix"])
    existing = next((a for a in adapter["addresses"] if a["address"] == config["address"] and a["prefix"] == config["prefix"]), None)
    if config["mode"] == "keep" and not existing:
        raise NetworkError("IP انتخاب‌شده دیگر روی این کارت نیست؛ فهرست را تازه کنید. تنظیمات اینترنت تغییر نکرد.")
    if config["topology"] == "direct" or config["mode"] == "static":
        isolated_guard(adapter, inventory, net)
    if config["mode"] == "static" and not existing:
        if adapter["dhcp"] and not any(a["address"].startswith("169.254.") for a in adapter["addresses"]):
            raise NetworkError("کارت هنوز در حال دریافت IP خودکار است؛ صبر کنید تا کابل مستقیم شناسایی شود. DHCP در حال اتصال به مودم قطع نمی‌شود.")
        valid = [a for a in adapter["addresses"] if any(ipaddress.IPv4Address(a["address"]) in n for n in PRIVATE)]
        if valid:
            raise NetworkError("این کارت از قبل IP داخلی دارد؛ آن را حفظ کنید یا در تنظیمات ویندوز دستی اصلاح کنید. IP قبلی حذف نمی‌شود.")
    for other in inventory["adapters"]:
        if other["id"] != adapter["id"] and any(a["address"] == config["address"] for a in other["addresses"]):
            raise NetworkError("این IP روی کارت دیگری موجود است؛ IP دیگری انتخاب کنید.")
    warnings = ["DNS، gateway، مسیرها، اولویت کارت‌ها و کارت‌های اینترنت دست‌نخورده می‌مانند."]
    if config["mode"] == "static" and not existing and adapter["dhcp"]:
        warnings.append("فقط DHCPِ همین کارتِ کابل مستقیم خاموش می‌شود؛ DHCPِ کارت اینترنت تغییر نمی‌کند.")
    shared = config["topology"] != "direct"
    if shared and adapter.get("profile") == "Public":
        warnings.append("این شبکه عمومی است؛ دسترسیِ خودکار فقط با هویتِ همین شبکهٔ مورد تأیید محدود می‌شود؛ اشتراک فایل فعال نمی‌شود.")
    if shared and not adapter.get("networkId"):
        raise NetworkError("هویت شبکهٔ مشترک معلوم نشد؛ برای امنیت فایروال باز نشد. اتصال شبکه را کامل و دوباره بررسی کنید.")
    return {
        "config": config, "adapterName": adapter["name"], "subnet": str(net),
        "serverUrl": f'http://{config["address"]}:{config["port"]}',
        "addAddress": config["mode"] == "static" and not existing,
        "networkId": adapter.get("networkId") if shared else None,
        "warnings": warnings,
    }


def suggestions(inventory: dict) -> dict:
    result = {}
    for adapter in inventory["adapters"]:
        if not adapter["physical"] or adapter["kind"] not in {"wired", "wifi"}:
            continue
        existing = next((a for a in adapter["addresses"] if any(ipaddress.IPv4Address(a["address"]) in n for n in PRIVATE) and 16 <= a["prefix"] <= 30), None)
        if existing:
            result[adapter["id"]] = {**existing, "mode": "keep"}
            continue
        if adapter["kind"] != "wired" or adapter.get("gateways") or adapter.get("defaultRoute"):
            continue
        for third in range(50, 250):
            address = f"192.168.{third}.1"
            try:
                isolated_guard(adapter, inventory, network_of(address, 24))
            except NetworkError:
                continue
            result[adapter["id"]] = {"address": address, "prefix": 24, "mode": "static"}
            break
    return result
