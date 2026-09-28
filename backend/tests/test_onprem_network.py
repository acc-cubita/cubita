"""هیچ فرمانی شبکهٔ واقعی را تغییر نمی‌دهد؛ تصمیم‌ها و مرزِ اجرای OS آزموده می‌شوند."""

from copy import deepcopy
import base64
import json
import os
import subprocess
import uuid

import pytest

from app.onprem import network as n
from app.onprem import network_windows as w

LAN = str(uuid.UUID(int=1))
WIFI = str(uuid.UUID(int=2))


def adapter(id=LAN, *, address="192.168.50.1", **changes):
    return {"id": id, "index": 22, "name": "LAN [1]", "physical": True, "kind": "wired", "status": "Up",
            "dhcp": False, "addresses": [{"address": address, "prefix": 24}] if address else [],
            "gateways": [], "defaultRoute": False, "profile": "Public", "networkId": "network-1", **changes}


def inv(a=None, others=(), routes=()):
    return {"adapters": [a or adapter(), *others], "routes": list(routes)}


def config(**changes):
    return {"adapterId": LAN, "topology": "direct", "mode": "keep", "address": "192.168.50.1", "prefix": 24,
            "port": 8420, "startup": True, "staticConsent": False, **changes}


@pytest.mark.parametrize("address", ["1.1.1.1", "127.0.0.1", "169.254.1.1", "224.1.2.3", "::1", "bad", "192.168.50.0", "192.168.50.255"])
def test_rejects_unsafe_addresses(address):
    with pytest.raises(n.NetworkError):
        n.validate_config(config(address=address))


@pytest.mark.parametrize("patch", [{"prefix": 8}, {"prefix": True}, {"port": True}, {"port": 0}, {"startup": "yes"}, {"adapterId": "Ethernet"}, {"command": "evil"}, {"topology": "unknown"}])
def test_rejects_invalid_input(patch):
    with pytest.raises(n.NetworkError):
        n.validate_config(config(**patch))


def test_preserves_current_ip_when_public_profile_returns():
    before = inv()
    saved = deepcopy(before)
    plan = n.make_plan(config(), before)
    assert not plan["addAddress"] and plan["networkId"] is None
    assert plan["subnet"] == "192.168.50.0/24"
    assert plan["serverUrl"] == "http://192.168.50.1:8420"
    assert before == saved


@pytest.mark.parametrize("gateways,default", [(["192.168.50.254"], False), ([], True), (["fe80::1"], True)])
def test_refuses_static_and_direct_on_internet_card(gateways, default):
    a = adapter(address=None, dhcp=True, gateways=gateways, defaultRoute=default)
    with pytest.raises(n.NetworkError, match="اینترنت"):
        n.make_plan(config(mode="static", staticConsent=True), inv(a))


def test_static_requires_consent_and_direct_cable():
    for patch in ({"staticConsent": False}, {"topology": "wired-router"}):
        with pytest.raises(n.NetworkError):
            n.make_plan(config(**{"mode": "static", "staticConsent": True, **patch}), inv(adapter(address=None)))


def test_static_only_adds_on_empty_isolated_wired_card():
    a = adapter(address=None, dhcp=True, addresses=[{"address": "169.254.5.6", "prefix": 16}])
    plan = n.make_plan(config(mode="static", staticConsent=True), inv(a))
    assert plan["addAddress"] and any("DHCP" in x for x in plan["warnings"])
    with pytest.raises(n.NetworkError, match="از قبل"):
        n.make_plan(config(mode="static", staticConsent=True), inv(adapter(address="192.168.60.1")))


def test_dhcp_pending_on_boot_cannot_be_disabled_as_if_direct_cable():
    with pytest.raises(n.NetworkError, match="دریافت IP"):
        n.make_plan(config(mode="static", staticConsent=True), inv(adapter(address=None, dhcp=True)))


def test_startup_never_disables_dhcp_reenabled_by_user(tmp_path, monkeypatch):
    saved = config(mode="static", staticConsent=True)
    (tmp_path / "settings.json").write_text(json.dumps({"config": saved, "networkId": None}))
    calls = []
    for name in ("require_admin", "protect_root"):
        monkeypatch.setattr(w, name, lambda: None)
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "inventory", lambda: inv(adapter(address=None, dhcp=True, addresses=[{"address": "169.254.5.6", "prefix": 16}])))
    monkeypatch.setattr(w, "local_role", lambda: "client")
    monkeypatch.setattr(w, "ps", lambda script, data=None: calls.append(script))
    state = w.maintain()
    assert not state["enabled"] and "دوباره فعال" in state["message"]
    assert all("New-NetIPAddress" not in c for c in calls)


def test_no_deletion_if_requested_static_already_exists():
    assert not n.make_plan(config(mode="static", staticConsent=True), inv())["addAddress"]


@pytest.mark.parametrize("kind,physical", [("other", True), ("wired", False), ("wifi", True)])
def test_direct_cannot_mutate_wifi_vpn_or_virtual(kind, physical):
    with pytest.raises(n.NetworkError):
        n.make_plan(config(), inv(adapter(kind=kind, physical=physical)))


def test_overlapping_wifi_and_vpn_are_refused():
    with pytest.raises(n.NetworkError, match="تداخل"):
        n.make_plan(config(), inv(others=[adapter(WIFI)]))
    with pytest.raises(n.NetworkError, match="VPN"):
        n.make_plan(config(), inv(routes=[{"index": 30, "destination": "128.0.0.0/1"}]))


def test_shared_wifi_keeps_dhcp_and_internet_with_network_identity():
    a = adapter(kind="wifi", dhcp=True, gateways=["192.168.50.254"], defaultRoute=True)
    plan = n.make_plan(config(topology="wifi-router"), inv(a))
    assert not plan["addAddress"] and plan["networkId"] == "network-1"
    with pytest.raises(n.NetworkError, match="هویت"):
        n.make_plan(config(topology="wifi-router"), inv(adapter(kind="wifi", networkId=None)))


def test_keep_refuses_stale_ip_instead_of_overwriting_dhcp():
    with pytest.raises(n.NetworkError, match="دیگر"):
        n.make_plan(config(), inv(adapter(address="192.168.50.2")))


def test_suggestion_is_not_hardcoded_and_never_mutates():
    actual = inv(adapter(address=None), others=[adapter(WIFI)])
    saved = deepcopy(actual)
    assert n.suggestions(actual)[LAN]["address"] == "192.168.51.1"
    assert actual == saved


def test_scripts_do_not_reconfigure_internet_or_public_profile():
    scripts = w.APPLY + w.REGISTER + w.DISABLE
    for prohibited in ("Set-NetConnectionProfile", "Set-DnsClient", "Remove-NetIPAddress", "Set-NetIPInterface", "Disable-NetAdapter", "New-NetRoute", "Remove-NetRoute", "DefaultGateway"):
        assert prohibited not in scripts
    for scope in ("LocalPort", "LocalAddress", "RemoteAddress", "InterfaceAlias", "Protocol='TCP'"):
        assert scope in w.APPLY
    assert "WildcardPattern]::Escape" in w.APPLY
    assert "networkId" in w.APPLY
    assert "data.role -ne 'server'" in w.APPLY
    assert "AtStartup" in w.REGISTER and "Minutes 1" in w.REGISTER and "IgnoreNew" in w.REGISTER


def test_application_revalidates_and_persists_only_machine_config(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "require_admin", lambda: None)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "protect_root", lambda: None)
    monkeypatch.setattr(w, "inventory", inv)
    monkeypatch.setattr(w, "local_role", lambda: "server")
    monkeypatch.setattr(w, "check_server_port", lambda p: None)
    monkeypatch.setattr(w, "ps", lambda script, data=None: calls.append((script, data)))
    state = w.apply(config())
    assert state["enabled"]
    assert json.loads((tmp_path / "settings.json").read_text())["config"] == config()
    assert [c[0] for c in calls] == [w.NETWORK_IDS + w.APPLY, w.REGISTER]
    assert "DATABASE_URL" not in (tmp_path / "settings.json").read_text()


def test_maintain_disables_own_rule_on_network_change(tmp_path, monkeypatch):
    calls = []
    saved = config(topology="wifi-router")
    (tmp_path / "settings.json").write_text(json.dumps({"config": saved, "networkId": "old-network"}))
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "require_admin", lambda: None)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "protect_root", lambda: None)
    monkeypatch.setattr(w, "local_role", lambda: "server")
    monkeypatch.setattr(w, "check_server_port", lambda p: None)
    monkeypatch.setattr(w, "inventory", lambda: inv(adapter(kind="wifi")))
    monkeypatch.setattr(w, "ps", lambda script, data=None: calls.append(script))
    state = w.maintain()
    assert not state["enabled"] and "شبکه عوض" in state["message"]
    assert all(w.APPLY not in c for c in calls) and "Disable-NetFirewallRule" in calls[-1]


def test_dhcp_renewal_only_in_approved_subnet(tmp_path, monkeypatch):
    cfg = config(topology="wifi-router")
    (tmp_path / "settings.json").write_text(json.dumps({"config": cfg, "networkId": "network-1"}))
    calls = []
    for name in ("require_admin", "protect_root"):
        monkeypatch.setattr(w, name, lambda: None)
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "local_role", lambda: "server")
    monkeypatch.setattr(w, "check_server_port", lambda p: None)
    monkeypatch.setattr(w, "inventory", lambda: inv(adapter(kind="wifi", address="192.168.50.5", dhcp=True)))
    monkeypatch.setattr(w, "ps", lambda script, data=None: calls.append((script, data)))
    state = w.maintain()
    assert state["enabled"] and state["serverUrl"] == "http://192.168.50.5:8420"
    applied = next(c for c in calls if w.APPLY in c[0])
    assert not applied[1]["addAddress"]


@pytest.mark.skipif(os.name != "nt", reason="Windows subprocess encoding boundary")
def test_powershell_uses_encoded_json_not_interpolated_script(monkeypatch):
    captured = []
    monkeypatch.setattr(w.subprocess, "run", lambda args, **kw: captured.append(args) or subprocess.CompletedProcess(args, 0, '{"x":1}', ''))
    w.ps("$data.name", {"name": "'; Remove-Item /; '"})
    code = base64.b64decode(captured[0][-1]).decode("utf-16le")
    assert "Remove-Item" not in code and "FromBase64String" in code


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell sandbox")
@pytest.mark.parametrize("role,static,medium", [("server", False, 14), ("server", True, 14), ("client", True, 14), ("server", True, 0)])
def test_apply_script_with_mocked_os_commands(role, static, medium):
    # Rename every OS cmdlet before execution. A missing mock fails as an unknown
    # command; it cannot silently fall through to the real Windows cmdlet.
    script = w.APPLY
    names = ("Get-NetAdapter", "Get-NetRoute", "Get-NetIPAddress", "Get-NetIPInterface", "Get-NetFirewallRule", "New-NetIPAddress", "Set-NetFirewallRule", "New-NetFirewallRule", "Remove-NetFirewallRule")
    for name in names:
        script = script.replace(name, "Mock-" + name)
    sandbox = r"""
$script:calls = @()
$script:addresses = @([pscustomobject]@{IPAddress=$data.config.address; PrefixLength=24; AddressState='Preferred'})
if($data.addAddress) { $script:addresses=@([pscustomobject]@{IPAddress='169.254.5.6'; PrefixLength=16; AddressState='Preferred'}) }
function Mock-Get-NetAdapter { [pscustomobject]@{InterfaceGuid=[Guid]$data.config.adapterId; InterfaceIndex=22; Name='LAN [1]'; HardwareInterface=$true; NdisPhysicalMedium=$data.medium; InterfaceType=6; Status='Up'} }
function Mock-Get-NetRoute { @() }
function Mock-Get-NetIPInterface { [pscustomobject]@{Dhcp='Enabled'} }
function Mock-Get-NetIPAddress {
  param($InterfaceIndex,$AddressFamily,$IPAddress)
  if($IPAddress) { $script:addresses | Where-Object { $_.IPAddress -eq $IPAddress } } else { $script:addresses }
}
function Mock-New-NetIPAddress {
  param($InterfaceIndex,$IPAddress,$PrefixLength)
  $script:calls+=@{kind='ip'; address=$IPAddress; prefix=$PrefixLength}
  $script:addresses=@([pscustomobject]@{IPAddress=$IPAddress; PrefixLength=$PrefixLength; AddressState='Preferred'})
}
function Mock-Get-NetFirewallRule { $null }
function Mock-New-NetFirewallRule {
  param($Name,$DisplayName,$Direction,$Action,$Enabled,$Profile,$Protocol,$LocalPort,$LocalAddress,$RemoteAddress,$InterfaceAlias)
  $script:calls+=@{kind='firewall'; port=$LocalPort; local=$LocalAddress; remote=$RemoteAddress; alias=$InterfaceAlias; profile=$Profile; protocol=$Protocol}
}
function Mock-Set-NetFirewallRule { throw 'not expected in this sandbox' }
function Mock-Remove-NetFirewallRule { $script:calls+=@{kind='remove'} }
"""
    data = {"config": config(mode="static" if static else "keep", staticConsent=static), "role": role, "addAddress": static, "networkId": None, "subnet": "192.168.50.0/24", "medium": medium}
    result = json.loads(w.ps(sandbox + "\n& {\n" + script + "\n}\n@{calls=$script:calls}|ConvertTo-Json -Depth 6 -Compress", data))
    calls = result["calls"]
    assert any(c["kind"] == "ip" for c in calls) == static
    if role == "server":
        rule = next(c for c in calls if c["kind"] == "firewall")
        assert rule == {"kind": "firewall", "port": 8420, "local": "192.168.50.1", "remote": "192.168.50.0/24", "alias": "LAN `[1`]", "profile": "Any", "protocol": "TCP"}
    else:
        assert not any(c["kind"] == "firewall" for c in calls)


def test_server_port_cannot_open_unrelated_service(tmp_path, monkeypatch):
    (tmp_path / "Cubita").mkdir()
    (tmp_path / "Cubita/.env").write_text("API_PORT=8425\nDATABASE_URL=not-for-output\n")
    monkeypatch.setenv("ProgramData", str(tmp_path))
    with pytest.raises(n.NetworkError, match="8425"):
        w.check_server_port({"role": "server", "config": config()})
    w.check_server_port({"role": "server", "config": config(port=8425)})
    w.check_server_port({"role": "client", "config": config()})


@pytest.mark.parametrize("contents", ["broken-json", '{}', '[]'])
def test_invalid_startup_settings_close_only_own_rule(tmp_path, monkeypatch, contents):
    (tmp_path / "settings.json").write_text(contents)
    calls = []
    for name in ("require_admin", "protect_root"):
        monkeypatch.setattr(w, name, lambda: None)
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "ps", lambda script, data=None: calls.append(script))
    state = w.maintain()
    assert not state["enabled"] and "config" not in state
    assert "Disable-NetFirewallRule" in calls[-1]
    assert all("New-NetIPAddress" not in c for c in calls)


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduled-task construction")
def test_task_construction_without_registration():
    # The New-* cmdlets construct objects only. Replace the sole OS write command.
    sandbox = r"""
function Mock-Register-ScheduledTask {
  param($TaskName,$Action,$Trigger,$Settings,$Principal,[switch]$Force)
  @{name=$TaskName; exe=$Action.Execute; argument=$Action.Arguments; triggers=$Trigger.Count;
    interval=$Trigger[1].Repetition.Interval; duration=$Trigger[1].Repetition.Duration;
    principal=$Principal.UserId; limit=$Settings.ExecutionTimeLimit} | ConvertTo-Json -Compress
}
"""
    result = json.loads(w.ps(sandbox + w.REGISTER.replace("Register-ScheduledTask", "Mock-Register-ScheduledTask").replace(" | Out-Null", ""), {"exe": r"C:\Program Files\Cubita Enterprise\resources\server\cubita-server.exe"}))
    assert result["name"] == w.TASK and result["argument"] == "network-maintain"
    assert result["triggers"] == 2 and result["interval"] == "PT1M"
    assert not result["duration"] and result["limit"] == "PT50S"
    assert result["principal"] in {"SYSTEM", "S-1-5-18"}


def test_validation_failure_updates_status_instead_of_showing_old_success(tmp_path, monkeypatch):
    for name in ("require_admin", "protect_root"):
        monkeypatch.setattr(w, name, lambda: None)
    monkeypatch.setattr(w, "root", lambda: tmp_path)
    monkeypatch.setattr(w, "trusted_executable", lambda: tmp_path / "cubita-server.exe")
    monkeypatch.setattr(w, "inventory", inv)
    monkeypatch.setattr(w, "local_role", lambda: "server")
    monkeypatch.setattr(w, "check_server_port", lambda p: (_ for _ in ()).throw(n.NetworkError("پورت اشتباه")))
    monkeypatch.setattr(w, "ps", lambda script, data=None: None)
    (tmp_path / "state.json").write_text(json.dumps({"enabled": True, "message": "old success"}))
    with pytest.raises(n.NetworkError, match="پورت"):
        w.apply(config())
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert not state["enabled"] and state["message"] == "پورت اشتباه"


def test_cleanup_failure_keeps_both_actionable_errors(monkeypatch):
    monkeypatch.setattr(w, "ps", lambda *a: (_ for _ in ()).throw(n.NetworkError("فایروال در دسترس نیست")))
    message = w.close_rule_on_error("خطای IP")
    assert "خطای IP" in message and "فایروال در دسترس نیست" in message


@pytest.mark.skipif(os.name != "nt", reason="Windows inventory sandbox")
@pytest.mark.parametrize("interface_type,kind", [(6, "wired"), (71, "wifi")])
def test_unspecified_driver_medium_falls_back_to_interface_type(interface_type, kind):
    script = w.INVENTORY
    for name in ("Get-NetRoute", "Get-NetAdapter", "Get-NetIPInterface", "Get-NetConnectionProfile", "Get-NetIPAddress"):
        script = script.replace(name, "Mock-" + name)
    sandbox = r"""
$networkIds=@{}
function Mock-Get-NetRoute { @() }
function Mock-Get-NetAdapter { [pscustomobject]@{InterfaceGuid=[Guid]$data.id; InterfaceIndex=22; Name='USB adapter'; HardwareInterface=$true; NdisPhysicalMedium=0; InterfaceType=$data.type; Status='Up'} }
function Mock-Get-NetIPInterface { [pscustomobject]@{Dhcp='Enabled'} }
function Mock-Get-NetConnectionProfile { [pscustomobject]@{NetworkCategory='Public'} }
function Mock-Get-NetIPAddress { [pscustomobject]@{IPAddress='192.168.50.5'; PrefixLength=24; AddressState='Preferred'; PrefixOrigin='Dhcp'} }
"""
    result = json.loads(w.ps(sandbox + script, {"id": LAN, "type": interface_type}))
    assert result["adapters"][0]["kind"] == kind
    assert result["adapters"][0]["physical"]
