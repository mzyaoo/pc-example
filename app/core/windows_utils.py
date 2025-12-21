import ctypes
import sys


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
