import ctypes
import datetime
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


def filetime_to_str(ft):
    """
    将 Windows FILETIME 结构转换为可读字符串 (YYYY-MM-DD HH:MM:SS)
    """
    # 组合高位和低位得到 64 位整数
    quad = (ft.dwHighDateTime << 32) | ft.dwLowDateTime

    # Windows FILETIME 是自 1601-01-01 起的 100纳秒间隔
    # Unix 时间戳是自 1970-01-01 起的秒数
    # 两者相差 116444736000000000 个 100纳秒单位

    # 如果文件时间为0（无效），直接返回空
    if quad == 0:
        return ""

    try:
        # 转换为 Unix 时间戳 (秒)
        unix_timestamp = (quad - 116444736000000000) / 10000000
        # 格式化为本地时间字符串
        return datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, ValueError):
        # 处理某些极端异常的时间戳
        return ""


def format_size(size_bytes):
    """
    将字节大小转换为 KB, MB, GB 格式
    """
    KB = 1024
    MB = KB * 1024
    GB = MB * 1024

    if size_bytes >= GB:
        return f"{size_bytes / GB:.2f} GB"
    elif size_bytes >= MB:
        return f"{size_bytes / MB:.2f} MB"
    elif size_bytes >= KB:
        return f"{size_bytes / KB:.2f} KB"
    else:
        return f"{size_bytes} B"