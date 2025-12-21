import ctypes
import sys
from typing import List


def is_admin() -> bool:
    """检查当前脚本是否以管理员权限运行。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def relaunch_as_admin():
    """触发 UAC 提升权限重新运行脚本。"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


def get_available_drives() -> List[str]:
    """
    获取系统可用磁盘盘符
    返回格式: ["C:\\", "D:\\", "E:\\"]
    """
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()

    for i, letter in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        if bitmask & (1 << i):
            if letter not in ('A', 'B'):
                drives.append(f"{letter}:\\")

    return drives
