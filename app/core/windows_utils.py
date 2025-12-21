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
    获取磁盘信息
    :param self:
    :return:
    """
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if bitmask & 1:
            # 过滤掉 A 和 B 盘（通常是软驱）
            if letter not in 'AB':
                drives.append(letter)
        bitmask >>= 1
    return drives
