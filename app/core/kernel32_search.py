import ctypes
import os
import time
import pickle

from ctypes import wintypes
from collections import defaultdict
from app.core.windows_utils import get_available_drives

# kernel32 设置
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
FILE_ATTRIBUTE_DIRECTORY = 0x10


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


kernel32.FindFirstFileW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(WIN32_FIND_DATAW)]
kernel32.FindFirstFileW.restype = wintypes.HANDLE
kernel32.FindNextFileW.argtypes = [wintypes.HANDLE, ctypes.POINTER(WIN32_FIND_DATAW)]
kernel32.FindNextFileW.restype = wintypes.BOOL
kernel32.FindClose.argtypes = [wintypes.HANDLE]
kernel32.FindClose.restype = wintypes.BOOL

FILE_TYPE_MAP = {
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"],
    "文档": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".ods", ".odp"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"],
    "音频": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "代码": [".py", ".js", ".html", ".css", ".cpp", ".c", ".java", ".cs", ".php", ".vb", ".xml", ".json", ".yaml",
             ".yml"],
    "可执行文件": [".exe", ".msi", ".bat", ".cmd", ".ps1"]
}


# -------------------
# 文件搜索器
# -------------------
class DiskIndexer:
    def __init__(self, index_file="search_index.pkl"):
        self.index_file = index_file
        self.index = defaultdict(list)

    def build_index(self, drives=None, force=False):
        if not force and os.path.exists(self.index_file):
            self.load_index()
            print("[✓] 已加载现有索引")
            return

        if drives is None:
            # 全盘
            drives = get_available_drives()

        print(f"[+] 开始全盘索引: {', '.join(drives)}")
        start = time.time()
        for d in drives:
            self._scan_dir(d)
        print(f"[✓] 全盘索引完成，耗时 {time.time() - start:.2f}s")
        print(f"[✓] 文件总数: {sum(len(v) for v in self.index.values())}")

        self.save_index()

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
                        self._scan_dir(full_path)
                    else:
                        # 文件大小 = (High << 32) + Low
                        size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
                        self.index[name.lower()].append({"path": full_path, "size": size, "name": name})

                if not kernel32.FindNextFileW(hFind, ctypes.byref(find_data)):
                    break
        finally:
            kernel32.FindClose(hFind)

    def search(self, keyword, file_type=None):
        """
        搜索文件
        - keyword: 文件名关键字
        - file_type: FILE_TYPE_MAP 中的大类，如 "图片"、"文档"
        """
        keyword = keyword.lower()
        results = []

        extensions = None
        if file_type and file_type in FILE_TYPE_MAP:
            extensions = set(ext.lower() for ext in FILE_TYPE_MAP[file_type])

        for name, items in self.index.items():
            if keyword in name:
                for item in items:
                    if extensions:
                        ext = os.path.splitext(item["name"])[1].lower()
                        if ext not in extensions:
                            continue
                    results.append(item)
        return results

    def save_index(self):
        with open(self.index_file, "wb") as f:
            pickle.dump(dict(self.index), f)
        print(f"[✓] 索引已保存到 {self.index_file}")

    def load_index(self):
        with open(self.index_file, "rb") as f:
            self.index = pickle.load(f)
        print(f"[✓] 索引文件 {self.index_file} 加载完成")

    def rebuild_index(self, drives=None):
        """
        强制重建索引（覆盖更新）
        - 清空内存索引
        - 删除旧索引文件
        - 重新全盘扫描
        """
        print("[!] 强制重建索引中...")

        # 1. 清空内存索引
        self.index = defaultdict(list)

        # 2. 删除旧索引文件（如果存在）
        if os.path.exists(self.index_file):
            os.remove(self.index_file)
            print(f"[✓] 已删除旧索引文件: {self.index_file}")

        # 3. 重新构建索引
        if drives is None:
            drives = get_available_drives()

        print(f"[+] 开始全盘重建索引: {', '.join(drives)}")
        start = time.time()
        for d in drives:
            self._scan_dir(d)

        print(f"[✓] 索引重建完成，耗时 {time.time() - start:.2f}s")
        print(f"[✓] 文件总数: {sum(len(v) for v in self.index.values())}")

        # 4. 覆盖保存
        self.save_index()


if __name__ == "__main__":
    indexer = DiskIndexer()
    indexer.build_index()

    # 交互搜索
    while True:
        key = input("\n请输入文件名（exit 退出）: ").strip()
        if key.lower() == "exit":
            break
        res = indexer.search(key)
        if not res:
            print("未找到")
        else:
            print(f"找到 {len(res)} 个结果：")
            for p in res:
                print(" ", p)
