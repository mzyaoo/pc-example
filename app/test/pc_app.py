import winreg
import subprocess
import psutil
import win32com.client






def get_physical_memory_total() -> dict:
    """
    获取 Windows 物理内存总量
    :return: dict，单位为字节和 GB
    """
    mem = psutil.virtual_memory()

    total_bytes = mem.total
    total_gb = round(total_bytes / (1024 ** 3), 2)

    return {
        "total_bytes": total_bytes,
        "total_gb": total_gb
    }


def set_reg(name: str, value: int):
    """设置注册表 DWORD 值"""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        REG_PATH,
        0,
        winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)


def refresh_theme():
    """
    刷新系统主题（不需要重启）
    """
    # 通知系统配置发生变化
    subprocess.run(
        ["powershell", "-Command", "Stop-Process -Name explorer -Force"],
        shell=True
    )


def set_dark_mode():
    set_reg("AppsUseLightTheme", 0)
    set_reg("SystemUsesLightTheme", 0)
    refresh_theme()


def set_light_mode():
    set_reg("AppsUseLightTheme", 1)
    set_reg("SystemUsesLightTheme", 1)
    refresh_theme()

def set_default_mode():
    set_light_mode()



def run(cmd: str):
    subprocess.run(cmd, shell=True, check=True)


def set_best_efficiency():
    run("powercfg /setactive SCHEME_MAX")


def set_balanced():
    run("powercfg /setactive SCHEME_BALANCED")


def set_best_performance():
    run("powercfg /setactive SCHEME_MIN")



def reset():
    run("powercfg /restoredefaultschemes")


def get_current_scheme():
    r = subprocess.check_output("powercfg /getactivescheme", shell=True)
    return r.decode("gbk", errors="ignore")


def get_usb_devices():
    wmi = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    service = wmi.ConnectServer(".", "root\\cimv2")

    devices = []
    for dev in service.ExecQuery("SELECT * FROM Win32_PnPEntity"):
        if dev.PNPDeviceID and dev.PNPDeviceID.startswith("USB"):
            devices.append({
                "name": dev.Name,
                "device_id": dev.DeviceID,
                "pnp_id": dev.PNPDeviceID,
                "manufacturer": dev.Manufacturer,
                "class": dev.PNPClass
            })

    return devices

# if __name__ == "__main__":
#     print(get_current_scheme())
#     print("1 = 最佳能效模式")
#     print("2 = 平衡模式")
#     print("3 = 最佳性能模式")
#
#     choice = input("请选择：")
#
#     if choice == "1":
#         set_best_efficiency()
#     elif choice == "2":
#         set_balanced()
#     elif choice == "3":
#         set_best_performance()
#     else:
#         print("无效选择")


if __name__ == '__main__':
    # for d in get_usb_devices():
    #     print(d)

    # reset()
    print(get_physical_memory_total())