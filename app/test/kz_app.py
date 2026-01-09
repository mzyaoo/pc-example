import os
import subprocess
import webbrowser
import ctypes
from ctypes import wintypes
from typing import List


def _run(cmd: List[str], wait: bool = False) -> bool:
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait:
            p.wait(timeout=10)
        return True
    except Exception:
        return False

def open_settings_uri(uri: str) -> bool:
    """打开 ms-settings 协议页面"""
    try:
        os.startfile(uri)  # type: ignore
        return True
    except Exception:
        # 兜底用 cmd 启动
        return _run(["cmd", "/c", "start", "", uri])

def open_taskmgr() -> bool:
    return _run(["taskmgr.exe"])

def open_device_manager() -> bool:
    # devmgmt.msc 更通用
    return _run(["mmc.exe", "devmgmt.msc"]) or _run(["devmgmt.msc"])

def open_browser(url: str = "about:blank") -> bool:
    try:
        return webbrowser.open(url, new=1)
    except Exception:
        return False


def task_open_settings() -> dict:
    """打开设置"""
    ok = open_settings_uri("ms-settings:")
    return {"ok": ok, "action": "open_settings"}


def task_open_update_settings() -> dict:
    """打开更新设置"""
    ok = open_settings_uri("ms-settings:windowsupdate")
    return {"ok": ok, "action": "open_update_settings"}


def task_open_personalization_settings() -> dict:
    """打开个性化设置"""
    ok = open_settings_uri("ms-settings:personalization")
    return {"ok": ok, "action": "open_personalization_settings"}


def open_device_manager() -> bool:
    """打开设备管理器"""
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "devmgmt.msc"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def task_open_task_manager() -> dict:
    """打开任务管理器"""
    ok = open_taskmgr()
    return {"ok": ok, "action": "open_task_manager"}

def task_open_mobile_hotspot() -> dict:
    """打开热点"""
    ok = open_settings_uri("ms-settings:network-mobilehotspot")
    if not ok:
        # 兜底打开网络设置
        ok = open_settings_uri("ms-settings:network")
    return {"ok": ok, "action": "open_mobile_hotspot"}


def get_default_browser_prog_id_api() -> str | None:
    """
    使用 Windows API 获取 http 协议关联的 ProgID。
    这比直接读取注册表更准确。
    """
    try:
        # 加载 shlwapi.dll
        shlwapi = ctypes.windll.shlwapi

        # 定义常量
        ASSOCF_NONE = 0
        ASSOCSTR_PROGID = 20  # 请求返回 ProgID (如 ChromeHTML, MSEdgeHTM)

        # 准备输出缓冲区
        out_buf = ctypes.create_unicode_buffer(1024)
        out_len = wintypes.DWORD(1024)

        # 调用 AssocQueryStringW
        # 参数: flags, str_type, association(http), extra, out_buf, out_len
        result = shlwapi.AssocQueryStringW(
            ASSOCF_NONE,
            ASSOCSTR_PROGID,
            "http",
            None,
            out_buf,
            ctypes.byref(out_len)
        )

        # S_OK = 0
        if result == 0:
            return out_buf.value
        else:
            return None

    except Exception as e:
        print(f"Error checking association: {e}")
        return None

def open_default_browser(url: str = "about:blank") -> bool:
    """
    使用系统默认浏览器打开 URL
    """
    try:
        # 1) 最符合系统行为：ShellExecute
        r = ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
        return r > 32
    except Exception:
        pass

    try:
        # 2) 兜底：os.startfile（同样走 Shell）
        os.startfile(url)  # type: ignore
        return True
    except Exception:
        return False

PROGID_TO_PROCESS = {
    "ChromeHTML": "chrome.exe",
    "MSEdgeHTM": "msedge.exe",
    "FirefoxURL": "firefox.exe",
}

def restart_default_browser(url: str = "https://example.com") -> dict:
    """
    重启系统默认浏览器（工程级可行方案）
    """
    prog_id = get_default_browser_prog_id_api()
    proc_name = PROGID_TO_PROCESS.get(prog_id)

    killed = False

    if proc_name:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            killed = True
            # time.sleep(0.5)
        except Exception:
            pass

    opened = open_default_browser(url)

    return {
        "ok": opened,
        "action": "restart_default_browser",
        "prog_id": prog_id,
        "process": proc_name,
        "killed": killed,
        "url": url
    }


if __name__ == '__main__':
    # open_default_browser("https://www.baidu.com")
    # restart_default_browser("https://www.google.com")
    print(get_default_browser_prog_id_api())