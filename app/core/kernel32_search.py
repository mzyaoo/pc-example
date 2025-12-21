import ctypes
from ctypes import wintypes
import os
import time
from collections import defaultdict

# ===============================
# 1. 加载 kernel32.dll
# ===============================
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
FILE_ATTRIBUTE_DIRECTORY = 0x10

# ===============================
# 2. 定义 WIN32_FIND_DATAW
# ===============================
class WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("dwReserved0", wintypes.DWORD),
        ("dwReserved1", wintypes.DWORD),
        ("cFileName", wintypes.WCHAR * 260),
        ("cAlternateFileName", wintypes.WCHAR * 14),
    ]


# ===============================
# 3. API 函数签名
# ===============================
kernel32.FindFirstFileW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.POINTER(WIN32_FIND_DATAW)
]
kernel32.FindFirstFileW.restype = wintypes.HANDLE

kernel32.FindNextFileW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(WIN32_FIND_DATAW)
]
kernel32.FindNextFileW.restype = wintypes.BOOL

kernel32.FindClose.argtypes = [wintypes.HANDLE]
kernel32.FindClose.restype = wintypes.BOOL


# ===============================
# 4. 文件搜索器
# ===============================
class DiskIndexer:
    def __init__(self, drive="D:\\"):
        self.drive = drive
        self.index = defaultdict(list)

    def build_index(self):
        print(f"[+] 开始索引磁盘 {self.drive}")
        start = time.time()
        self._scan_dir(self.drive)
        print(f"[✓] 索引完成，耗时 {time.time() - start:.2f}s")
        print(f"[✓] 文件总数: {sum(len(v) for v in self.index.values())}")

    def _scan_dir(self, path):
        search_path = os.path.join(path, "*")
        find_data = WIN32_FIND_DATAW()

        hFind = kernel32.FindFirstFileW(search_path, ctypes.byref(find_data))
        if hFind == INVALID_HANDLE_VALUE:
            return

        try:
            while True:
                name = find_data.cFileName
                if name not in (".", ".."):
                    full_path = os.path.join(path, name)

                    is_dir = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY

                    if is_dir:
                        # 递归目录
                        self._scan_dir(full_path)
                    else:
                        # 文件入索引
                        self.index[name.lower()].append(full_path)

                if not kernel32.FindNextFileW(hFind, ctypes.byref(find_data)):
                    break
        finally:
            kernel32.FindClose(hFind)

    def search(self, keyword):
        """
        支持：
        - 完整文件名
        - 子串搜索
        """
        keyword = keyword.lower()
        results = []

        for name, paths in self.index.items():
            if keyword in name:
                results.extend(paths)

        return results


# ===============================
# 5. 使用示例
# ===============================
if __name__ == "__main__":
    indexer = DiskIndexer("C:\\")

    # ① 建立索引（只需一次）
    indexer.build_index()

    # ② 交互搜索
    while True:
        key = input("\n请输入文件名（exit 退出）: ").strip()
        if key == "exit":
            break

        res = indexer.search(key)
        if not res:
            print("未找到")
        else:
            print(f"找到 {len(res)} 个结果：")
            for p in res:
                print(" ", p)
