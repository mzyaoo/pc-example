import win32con
import win32gui


def get_all_windows():
    windows = []

    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append((hwnd, title))

    win32gui.EnumWindows(enum_handler, None)
    return windows


def maximize(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

def minimize(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

def restore(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

def activate(hwnd):
    win32gui.SetForegroundWindow(hwnd)

def close(hwnd):
    """
    正常关闭窗口（触发 WM_CLOSE）
    等同于用户点击右上角关闭按钮
    """
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

def find_window_by_title(keyword: str):
    for hwnd, title in get_all_windows():
        if keyword.lower() in title.lower():
            return hwnd, title
    return None, None

if __name__ == '__main__':
    for hwnd, title in get_all_windows():
        print(hex(hwnd), title)

    hwnd, title = find_window_by_title("设置")

    if hwnd:
        # activate(hwnd)
        close(hwnd)


