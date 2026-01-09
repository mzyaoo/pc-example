# -*- coding: utf-8 -*-
"""
Windows 系统信息采集（尽量完整 + 强兜底）
返回 dict，可直接 json.dumps 输出。

依赖建议：
pip install psutil requests pywin32 wmi tzlocal
"""

from __future__ import annotations

import time
import ctypes
import socket
import urllib
import webbrowser
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# --- optional deps ---
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore

try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

try:
    import winreg  # type: ignore
except Exception:
    winreg = None  # type: ignore

try:
    import wmi as wmi_lib  # type: ignore
except Exception:
    wmi_lib = None  # type: ignore

try:
    from tzlocal import get_localzone_name  # type: ignore
except Exception:
    get_localzone_name = None  # type: ignore


# ----------------------------
# Utils
# ----------------------------

def _bytes_to_gb(n: Optional[int]) -> Optional[float]:
    if n is None:
        return None
    return round(n / (1024 ** 3), 2)

def _safe_run(cmd: str, timeout: int = 5) -> Tuple[int, str]:
    """运行命令行，返回 (code, stdout_text)"""
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
        )
        out = (p.stdout or "").strip()
        if not out:
            out = (p.stderr or "").strip()
        return p.returncode, out
    except Exception as e:
        return 1, str(e)

def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _format_uptime(seconds: int) -> str:
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours or parts:
        parts.append(f"{hours}小时")
    if minutes or parts:
        parts.append(f"{minutes}分")
    parts.append(f"{seconds}秒")
    return "".join(parts)

def _now_local_str() -> str:
    # 本机当前时间（含日期）
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _get_timezone_str() -> str:
    # 尝试 tzlocal，否则退回 time.tzname
    try:
        if get_localzone_name:
            tzname = get_localzone_name()
        else:
            tzname = time.tzname[0] if time.tzname else "未知时区"
        # UTC offset
        # time.timezone: seconds west of UTC (negative means east)
        offset_sec = -time.timezone
        sign = "+" if offset_sec >= 0 else "-"
        offset_sec = abs(offset_sec)
        hh = offset_sec // 3600
        mm = (offset_sec % 3600) // 60
        return f"{tzname} (UTC{sign}{hh:02d}:{mm:02d})"
    except Exception:
        return "未知"

def _get_system_drive() -> str:
    return os.environ.get("SystemDrive", "C:") + "\\"


# ----------------------------
# CPU / MEM / DISK
# ----------------------------

# def get_cpu_model() -> Optional[str]:
#     # 1) WMI
#     if wmi_lib is not None:
#         try:
#             c = wmi_lib.WMI()
#             cpus = c.Win32_Processor()
#             if cpus:
#                 name = (cpus[0].Name or "").strip()
#                 return name or None
#         except Exception:
#             pass
#
#     # 2) WMIC（老但好用，Win11 可能还在）
#     code, out = _safe_run('wmic cpu get name /value')
#     if code == 0 and "Name=" in out:
#         m = re.search(r"Name=(.+)", out)
#         if m:
#             return m.group(1).strip() or None
#
#     # 3) platform fallback
#     try:
#         p = platform.processor()
#         return p.strip() or None
#     except Exception:
#         return None

import re
import platform
import subprocess

def _safe_run(cmd: str, timeout: int = 5):
    try:
        p = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="ignore"
        )
        out = (p.stdout or "").strip()
        if not out:
            out = (p.stderr or "").strip()
        return p.returncode, out
    except Exception as e:
        return 1, str(e)

def get_cpu_model() -> str | None:
    # 1) ✅ 最稳：PowerShell CIM（推荐）
    code, out = _safe_run(
        'powershell -NoProfile -Command "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"',
        timeout=5
    )
    if code == 0 and out:
        name = out.strip()
        if name and "Family" not in name:
            return name

    # 2) WMI（如果你装了 wmi 库）
    try:
        import wmi
        c = wmi.WMI()
        cpus = c.Win32_Processor()
        if cpus:
            name = (cpus[0].Name or "").strip()
            if name and "Family" not in name:
                return name
    except Exception:
        pass

    # 3) WMIC（部分系统可能没有）
    code, out = _safe_run("wmic cpu get Name /value", timeout=5)
    if code == 0 and "Name=" in out:
        m = re.search(r"Name=(.+)", out)
        if m:
            name = m.group(1).strip()
            if name and "Family" not in name:
                return name

    # 4) 最后兜底（可能就会是你看到的 Family/Model）
    p = (platform.processor() or "").strip()
    return p or None


def get_cpu_usage_percent() -> Optional[float]:
    if psutil is None:
        return None
    try:
        # interval=0.3 更接近“当前”
        return float(psutil.cpu_percent(interval=0.3))
    except Exception:
        return None

def get_memory_info() -> Dict[str, Any]:
    if psutil is None:
        return {
            "physical_total_gb": None,
            "physical_available_gb": None,
            "memory_used_percent": None,
        }
    try:
        vm = psutil.virtual_memory()
        return {
            "physical_total_gb": _bytes_to_gb(int(vm.total)),
            "physical_available_gb": _bytes_to_gb(int(vm.available)),
            "memory_used_percent": float(vm.percent),
        }
    except Exception:
        return {
            "physical_total_gb": None,
            "physical_available_gb": None,
            "memory_used_percent": None,
        }

def get_system_disk_info() -> Dict[str, Any]:
    if psutil is None:
        return {
            "system_disk_total_gb": None,
            "system_disk_free_gb": None,
            "system_disk_used_percent": None,
            "system_disk_mount": _get_system_drive(),
        }
    try:
        mount = _get_system_drive()
        du = psutil.disk_usage(mount)
        return {
            "system_disk_total_gb": _bytes_to_gb(int(du.total)),
            "system_disk_free_gb": _bytes_to_gb(int(du.free)),
            "system_disk_used_percent": float(du.percent),
            "system_disk_mount": mount,
        }
    except Exception:
        return {
            "system_disk_total_gb": None,
            "system_disk_free_gb": None,
            "system_disk_used_percent": None,
            "system_disk_mount": _get_system_drive(),
        }


# ----------------------------
# GPU (model + temperature best-effort)
# ----------------------------

def get_gpu_models() -> List[str]:
    # 多显卡可能返回多个
    models: List[str] = []

    # 1) WMI Win32_VideoController
    if wmi_lib is not None:
        try:
            c = wmi_lib.WMI()
            gpus = c.Win32_VideoController()
            for g in gpus:
                name = (getattr(g, "Name", "") or "").strip()
                if name and name not in models:
                    models.append(name)
        except Exception:
            pass

    # 2) dxdiag 兜底（较慢，尽量不用）
    if not models:
        code, out = _safe_run('powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"')
        if code == 0 and out:
            for line in out.splitlines():
                name = line.strip()
                if name and name not in models:
                    models.append(name)

    return models

def filter_physical_gpus(gpu_models: list[str]) -> list[str]:
    blacklist_keywords = [
        "idd",
        "virtual",
        "mirror",
        "remote",
        "oray",
        "basic display",
    ]

    result = []
    for name in gpu_models:
        lname = name.lower()
        if any(k in lname for k in blacklist_keywords):
            continue
        result.append(name)

    return result


def get_gpu_temperature_c() -> Optional[float]:
    """
    GPU 温度在 Windows 上没有统一官方接口。
    这里做 best-effort：
    1) 优先 nvidia-smi（仅 NVIDIA 且驱动自带）
    2) 其次尝试 OpenHardwareMonitor 的 WMI（如果你装了并开启 WMI）
    """
    # 1) NVIDIA
    code, out = _safe_run('nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits', timeout=3)
    if code == 0 and out:
        try:
            # 可能多卡多行，取第一张
            first = out.splitlines()[0].strip()
            return float(first)
        except Exception:
            pass

    # 2) OpenHardwareMonitor (可选)
    # 需要你安装 OpenHardwareMonitor 并启用 WMI (root\OpenHardwareMonitor)
    if wmi_lib is not None:
        try:
            c = wmi_lib.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = c.Sensor()
            # 找 GPU 温度
            candidates = []
            for s in sensors:
                if getattr(s, "SensorType", "") == "Temperature":
                    name = str(getattr(s, "Name", "")).lower()
                    if "gpu" in name:
                        val = getattr(s, "Value", None)
                        if val is not None:
                            candidates.append(float(val))
            if candidates:
                return max(candidates)
        except Exception:
            pass

    return None


# ----------------------------
# Battery
# ----------------------------

def get_battery_info() -> Dict[str, Any]:
    if psutil is None:
        return {"battery_percent": None, "battery_status": "未知"}
    try:
        b = psutil.sensors_battery()
        if b is None:
            return {"battery_percent": None, "battery_status": "无电池"}
        percent = None if b.percent is None else float(b.percent)
        if b.power_plugged is True:
            if percent is not None and percent >= 99:
                status = "已充满"
            else:
                status = "正在充电"
        else:
            status = "未充电"
        return {"battery_percent": percent, "battery_status": status}
    except Exception:
        return {"battery_percent": None, "battery_status": "未知"}


# ----------------------------
# OS name/version (Windows edition + display version)
# ----------------------------

def _read_reg_str(root, path: str, name: str) -> Optional[str]:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v)
    except Exception:
        return None

def get_windows_os_name_version() -> str | None:
    """
    正确识别 Windows 10 / 11（不再误判）
    输出示例：
    Windows 11 家庭中文版 25H2 (Build 26200.7462)
    """
    try:
        path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            product_name = winreg.QueryValueEx(k, "ProductName")[0]
            display_version = winreg.QueryValueEx(k, "DisplayVersion")[0]
            build = winreg.QueryValueEx(k, "CurrentBuildNumber")[0]
            ubr = winreg.QueryValueEx(k, "UBR")[0]  # 修订号

        build_int = int(build)

        # ⭐ 唯一正确判定方式
        if build_int >= 22000:
            windows_name = "Windows 11"
        else:
            windows_name = "Windows 10"

        # ProductName 示例：
        # Windows 11 Home China
        # Windows 11 Pro
        edition = product_name.replace("Windows 11", "").replace("Windows 10", "").strip()

        return f"{windows_name} {edition} {display_version} (Build {build}.{ubr})"

    except Exception:
        return None


# ----------------------------
# Installed applications list (registry uninstall keys)
# ----------------------------

def get_installed_apps(limit: Optional[int] = None) -> List[str]:
    """
    从卸载注册表项读取已安装程序名称（不保证 100% 准确，但常用且快）。
    """
    if winreg is None:
        return []

    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    apps = set()

    for root, path in uninstall_paths:
        try:
            with winreg.OpenKey(root, path) as key:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(key, sub) as sk:
                            name, _ = winreg.QueryValueEx(sk, "DisplayName")
                            name = str(name).strip()
                            if name:
                                apps.add(name)
                    except Exception:
                        continue
        except Exception:
            continue

    res = sorted(apps)
    if limit is not None:
        res = res[:limit]
    return res


# ----------------------------
# Foreground window app name (exe)
# ----------------------------

def get_foreground_app_name() -> Optional[str]:
    """
    返回当前最前端窗口所属进程的 exe 名称（如 chrome.exe）
    仅 Windows。
    """
    if psutil is None:
        return None

    try:
        user32 = ctypes.windll.user32
        pid = ctypes.c_ulong(0)

        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return None
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        p = psutil.Process(pid.value)
        # exe path -> basename
        exe = p.exe()
        return os.path.basename(exe) if exe else (p.name() if p.name() else None)
    except Exception:
        return None


# ----------------------------
# Process count
# ----------------------------

def get_process_count() -> Optional[int]:
    if psutil is None:
        return None
    try:
        return len(psutil.pids())
    except Exception:
        return None


# ----------------------------
# Network status / IP / Wi-Fi SSID
# ----------------------------

def get_network_status() -> str:
    if psutil is None:
        # 简单兜底：能解析到 DNS 就认为在线
        try:
            socket.gethostbyname("www.baidu.com")
            return "已连接"
        except Exception:
            return "未连接"

    try:
        stats = psutil.net_if_stats()
        # 有任意接口 up 且非 loopback 就算连接
        for name, st in stats.items():
            if st.isup and "loopback" not in name.lower():
                return "已连接"
        return "未连接"
    except Exception:
        return "未知"

def get_active_local_ip() -> Optional[str]:
    """
    尽量拿“当前活动网络连接”的本机 IP（优先非回环 IPv4）。
    """
    if psutil is None:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None

    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        candidates = []
        for ifname, addr_list in addrs.items():
            st = stats.get(ifname)
            if not st or not st.isup:
                continue
            for a in addr_list:
                # AF_INET = IPv4
                if getattr(a, "family", None) == socket.AF_INET:
                    ip = a.address
                    if ip and not ip.startswith("127."):
                        candidates.append(ip)
        return candidates[0] if candidates else None
    except Exception:
        return None

def get_wifi_ssid() -> Optional[str]:
    """
    仅在 Wi-Fi 连接时有效。使用 netsh 解析。
    """
    code, out = _safe_run("netsh wlan show interfaces", timeout=3)
    if code != 0 or not out:
        return None
    # 中文系统常见：SSID                   : xxx
    m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
    if m:
        ssid = m.group(1).strip()
        if ssid and ssid.lower() != "n/a":
            return ssid
    return None


# ----------------------------
# External devices (USB / HID / printers) via WMI
# ----------------------------

def get_external_devices() -> Dict[str, Any]:
    """
    返回：
    - devices: [ "USB 鼠标 ...", "打印机 ..." ]
    - overall_status: "全部正常" / "有设备异常" / "未知"
    """
    devices: List[str] = []
    has_error = False

    if wmi_lib is None:
        return {"devices": [], "overall_status": "未知"}

    try:
        c = wmi_lib.WMI()
        # Win32_PnPEntity: 包含大量设备，这里筛 USB / HID / Printer 等关键词
        for d in c.Win32_PnPEntity():
            name = (getattr(d, "Name", "") or "").strip()
            pnpid = (getattr(d, "PNPDeviceID", "") or "").upper()
            status = (getattr(d, "Status", "") or "").strip()
            # ConfigManagerErrorCode: 0 = OK
            err = getattr(d, "ConfigManagerErrorCode", None)

            is_usb = "USB" in pnpid or "USB" in name.upper()
            is_hid = "HID" in pnpid or "HID" in name.upper()
            is_printer = "PRINT" in pnpid or "PRINTER" in name.upper() or "打印" in name

            if not (is_usb or is_hid or is_printer):
                continue

            if name:
                devices.append(name)

            if err is not None and int(err) != 0:
                has_error = True
            if status and status.lower() not in ("ok", "正常"):
                # status 字段不总可靠，但作为辅助
                if status.lower() not in ("unknown", "未知"):
                    has_error = True

        # 去重
        devices = sorted(set(devices))

        if not devices:
            return {"devices": [], "overall_status": "未知"}

        overall = "有设备异常" if has_error else "全部正常"
        return {"devices": devices, "overall_status": overall}
    except Exception:
        return {"devices": [], "overall_status": "未知"}


# ----------------------------
# City by IP + Weather (best-effort, needs internet)
# ----------------------------

def get_city_by_ip() -> Optional[str]:
    """
    通过 IP 粗略定位城市（需要联网）。
    使用 ip-api.com（免费，无 key，可能会有频控/限制）。
    """
    if requests is None:
        return None
    try:
        r = requests.get("http://ip-api.com/json/?fields=status,city,regionName,country", timeout=3)
        data = r.json()
        if data.get("status") == "success":
            city = data.get("city") or ""
            region = data.get("regionName") or ""
            country = data.get("country") or ""
            # 优先 city，否则 region
            return (city or region or country).strip() or None
        return None
    except Exception:
        return None

def get_weather_by_ip() -> Optional[str]:
    """
    用 IP 拿经纬度 -> Open-Meteo 获取当前天气（无 key）。
    需要联网。
    """
    if requests is None:
        return None
    try:
        # 1) ip-api 拿 lat/lon
        r = requests.get("http://ip-api.com/json/?fields=status,lat,lon", timeout=3)
        j = r.json()
        if j.get("status") != "success":
            return None
        lat, lon = j.get("lat"), j.get("lon")
        if lat is None or lon is None:
            return None

        # 2) Open-Meteo 当前天气
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code"
            "&timezone=auto"
        )
        r2 = requests.get(url, timeout=3)
        j2 = r2.json()
        cur = (j2.get("current") or {})
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code")

        # 简单 code 映射（可自行扩展）
        code_map = {
            0: "晴",
            1: "晴间多云", 2: "多云", 3: "阴",
            45: "雾", 48: "雾凇",
            51: "毛毛雨", 53: "小雨", 55: "中雨",
            61: "小雨", 63: "中雨", 65: "大雨",
            71: "小雪", 73: "中雪", 75: "大雪",
            80: "阵雨", 81: "阵雨", 82: "强阵雨",
            95: "雷暴",
        }
        desc = code_map.get(code, "未知天气")
        if temp is None:
            return desc
        return f"{desc}，{temp}°C"
    except Exception:
        return None


# ----------------------------
# Aggregator
# ----------------------------

def collect_system_snapshot(include_installed_apps: bool = True, apps_limit: Optional[int] = None) -> Dict[str, Any]:
    mem = get_memory_info()
    disk = get_system_disk_info()
    battery = get_battery_info()
    devices = get_external_devices()

    cpu_model = get_cpu_model()
    cpu_usage = get_cpu_usage_percent()

    gpu_models = filter_physical_gpus(get_gpu_models())

    gpu_temp = get_gpu_temperature_c()

    os_name_ver = get_windows_os_name_version()

    foreground_app = get_foreground_app_name()
    proc_count = get_process_count()

    net_status = get_network_status()
    local_ip = get_active_local_ip()
    wifi_ssid = get_wifi_ssid()

    admin = _is_admin()

    # uptime
    uptime_str = None
    if psutil is not None:
        try:
            boot = int(psutil.boot_time())
            uptime_seconds = int(time.time()) - boot
            uptime_str = _format_uptime(max(uptime_seconds, 0))
        except Exception:
            uptime_str = None

    # time/timezone
    sys_time = _now_local_str()
    tz_str = _get_timezone_str()

    # location/weather (needs internet)
    city = get_city_by_ip()
    weather = get_weather_by_ip()

    apps: List[str] = []
    if include_installed_apps:
        apps = get_installed_apps(limit=apps_limit)

    return {
        "cpu_model": cpu_model,  # Intel Core i7-12700H
        "cpu_usage_percent": cpu_usage,  # 0-100

        "physical_memory_total_gb": mem["physical_total_gb"],
        "physical_memory_available_gb": mem["physical_available_gb"],
        "memory_usage_percent": mem["memory_used_percent"],

        "system_disk_total_gb": disk["system_disk_total_gb"],
        "system_disk_free_gb": disk["system_disk_free_gb"],
        "system_disk_usage_percent": disk["system_disk_used_percent"],
        "system_disk_mount": disk["system_disk_mount"],

        "gpu_models": gpu_models,  # 主显卡/独显可能多个
        "gpu_temperature_c": gpu_temp,  # 可能 None

        "battery_percent": battery["battery_percent"],
        "battery_status": battery["battery_status"],

        "os_name_version": os_name_ver,

        "installed_apps": apps,  # JSON 数组
        "foreground_app_name": foreground_app,  # 最前端活动窗口程序名（exe）
        "process_count": proc_count,

        "network_status": net_status,
        "local_ip": local_ip,
        "wifi_ssid": wifi_ssid,

        "is_admin": "是" if admin else "否",
        "uptime": uptime_str,

        "external_devices": devices["devices"],
        "external_devices_overall_status": devices["overall_status"],

        "system_time": sys_time,
        "timezone": tz_str,

        "city_by_ip": city,
        "weather_now": weather,
    }

def search_baidu(keyword: str):
    q = urllib.parse.quote(keyword)
    webbrowser.open(f"https://www.baidu.com/s?wd={q}")


def open_amap_search(keyword: str):
    q = urllib.parse.quote(keyword)
    url = f"https://www.amap.com/search?query={q}"
    webbrowser.open(url)

def open_taobao_search(keyword: str):
    q = urllib.parse.quote(keyword)
    url = f"https://s.taobao.com/search?q={q}"
    os.startfile(url)


def open_12306_train(from_city: str, to_city: str):
    url = (
        "https://kyfw.12306.cn/otn/leftTicket/init"
        f"?linktypeid=dc&fs={from_city}&ts={to_city}"
    )
    os.startfile(url)


import os
import urllib.parse

def ths_search_stock_no_sign(keyword: str):
    q = urllib.parse.quote(keyword)
    url = f"https://search.10jqka.com.cn/unifiedwap/result?w={q}&querytype=stock"
    open_url(url)

def open_url(url: str):
    if platform.system() == "Windows":
        os.startfile(url)
    else:
        webbrowser.open(url)


def open_12306_left_ticket(fs: str, ts: str, d: str | None = None, flag: str = "N,N,Y"):
    """
    fs/ts 传入格式示例：
      fs="深圳北,IOQ"
      ts="上海,SHH"
    d:  "2026-01-09" ；不传则默认今天
    """
    if d is None:
        d = dt_date.today().isoformat()

    # 12306 参数里中文要 URL encode，但逗号和站码要保留
    fs_enc = urllib.parse.quote(fs, safe=",")
    ts_enc = urllib.parse.quote(ts, safe=",")

    url = (
        "https://kyfw.12306.cn/otn/leftTicket/init"
        f"?linktypeid=dc&fs={fs_enc}&ts={ts_enc}&date={d}&flag={flag}"
    )
    open_url(url)


if __name__ == "__main__":
    # ths_search_stock_no_sign("腾讯")
    open_12306_left_ticket("深圳", "上海", "2026-01-09")

    # open_taobao_search("奶瓶")
    # search_baidu("天气")
    # data = collect_system_snapshot(include_installed_apps=True, apps_limit=None)
    # print(json.dumps(data, ensure_ascii=False, indent=2))
