import ctypes
import os
import time
import pickle
import gzip
import sys

from ctypes import wintypes
from typing import Optional

from app.core.windows_utils import get_available_drives, filetime_to_str, format_size

# =========================
# Win32 API
# =========================
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

# =========================
# 文件类型映射
# =========================
FILE_TYPE_MAP = {
    "文档": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
    "音频": [".mp3", ".wav", ".flac", ".aac"],
    "文件夹": None,
    "其他": "others",
}


# =========================
# DiskIndexer
# =========================
class DiskIndexer:
    COMMON_SKIP_DIRS = {
        "windows",
        "system32",
        "syswow64",
        "winsxs",
        "system volume information",
        "$recycle.bin",
        "program files",
        "program files (x86)",
        "programdata",
        "appdata",
        "local settings",
        "temp",
        "tmp",
        "$windows.~bt",
        "$windows.~ws",
        "$getcurrent",
    }

    def __init__(
            self,
            index_file="kernel32_index.pkl.gz",
            skip_dirs=None,
            auto_build=True,
    ):
        self.index_file = index_file

        base_skip = set(map(str.lower, self.COMMON_SKIP_DIRS))
        user_skip = set(d.lower() for d in (skip_dirs or []))

        self.skip_dirs = base_skip | user_skip

        self.files = []
        self.file_map = {}
        self.meta = {}
        self.ready = False

        self._init_index(auto_build)

    # =========================
    # Index init
    # =========================
    def _init_index(self, auto_build):
        if os.path.exists(self.index_file):
            if self._try_load_index():
                self.ready = True
                return
            else:
                os.remove(self.index_file)

        if auto_build:
            self.build_index(force=True)
            self.ready = True

    # =========================
    # Build / Update
    # =========================
    def build_index(self, drives=None, force=False):
        if not force and self._try_load_index():
            return

        drives = drives or get_available_drives()

        self.files.clear()
        self.file_map.clear()

        for d in drives:
            self._scan_drive_full(d)

        self._build_meta(drives)
        self._save_index()

    def update_index(self, drives=None):
        if not self._try_load_index():
            self.build_index(drives, force=True)
            return

        drives = drives or self.meta["drives"]

        for d in drives:
            self._scan_drive_incremental(d)

        self.meta["updated_at"] = time.time()
        self.meta["total_files"] = len(self.files)
        self._save_index()

    # =========================
    # Scan logic
    # =========================
    def _scan_drive_full(self, root):
        stack = [root]

        while stack:
            path = stack.pop()
            h, fd = self._find_first(path)
            if not h:
                continue

            try:
                while True:
                    name = fd.cFileName
                    if name not in (".", ".."):
                        full = os.path.join(path, name)
                        is_dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY

                        if is_dir and name.lower() in self.skip_dirs:
                            pass
                        else:
                            item = self._build_item(fd, name, full, bool(is_dir))
                            self.files.append(item)
                            self.file_map[full] = item

                        if is_dir and name.lower() not in self.skip_dirs:
                            stack.append(full)

                    if not kernel32.FindNextFileW(h, ctypes.byref(fd)):
                        break
            finally:
                kernel32.FindClose(h)

    def _scan_drive_incremental(self, root):
        stack = [root]
        seen = set()

        while stack:
            path = stack.pop()
            h, fd = self._find_first(path)
            if not h:
                continue

            try:
                while True:
                    name = fd.cFileName
                    if name not in (".", ".."):
                        full = os.path.join(path, name)
                        is_dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
                        seen.add(full)

                        old = self.file_map.get(full)
                        if not old:
                            item = self._build_item(fd, name, full, bool(is_dir))
                            self.files.append(item)
                            self.file_map[full] = item
                        else:
                            if old["FP"] != self._fingerprint(fd):
                                self._update_item(old, fd)

                        if is_dir and name.lower() not in self.skip_dirs:
                            stack.append(full)

                    if not kernel32.FindNextFileW(h, ctypes.byref(fd)):
                        break
            finally:
                kernel32.FindClose(h)

        for p in list(self.file_map):
            if p.startswith(root) and p not in seen:
                self.files.remove(self.file_map[p])
                del self.file_map[p]

    # =========================
    # Helpers
    # =========================
    def _find_first(self, path):
        fd = WIN32_FIND_DATAW()
        h = kernel32.FindFirstFileW(os.path.join(path, "*"), ctypes.byref(fd))
        if h == INVALID_HANDLE_VALUE:
            return None, None
        return h, fd

    def _build_item(self, fd, name, full, is_dir):
        ts = (fd.ftLastWriteTime.dwHighDateTime << 32) | fd.ftLastWriteTime.dwLowDateTime
        size = 0 if is_dir else (fd.nFileSizeHigh << 32) + fd.nFileSizeLow
        ext = "" if is_dir else os.path.splitext(name)[1].lower()

        return {
            "Type": "DIR" if is_dir else "FILE",
            "Name": name,
            "NameLC": name.lower(),
            "Ext": ext,
            "Path": full,
            "RawSize": size,
            "UpdateTime": filetime_to_str(fd.ftLastWriteTime),
            "UpdateTS": ts,
            "FP": self._fingerprint(fd),
        }

    def _update_item(self, item, fd):
        item["RawSize"] = (fd.nFileSizeHigh << 32) + fd.nFileSizeLow
        item["UpdateTime"] = filetime_to_str(fd.ftLastWriteTime)
        item["FP"] = self._fingerprint(fd)

    @staticmethod
    def _fingerprint(fd):
        return (
            fd.nFileSizeHigh,
            fd.nFileSizeLow,
            fd.ftLastWriteTime.dwLowDateTime,
            fd.ftLastWriteTime.dwHighDateTime,
        )

    # =========================
    # Search
    # =========================
    def search(
            self,
            keywords: str,
            file_type: str,
            keyword_mode: str = "or",
            min_size: Optional[int] = None,
            max_size: Optional[int] = None,
            min_time: Optional[int] = None,
            max_time: Optional[int] = None,
            sort_by: str = "time",
            reverse: bool = True,
    ):
        if not keywords:
            return []

        # ---------- 关键词处理 ----------
        kws = [k.lower() for k in keywords.split() if k.strip()]
        if not kws:
            return []

        results = []
        append = results.append

        # ---------- 文件类型准备 ----------
        exts = FILE_TYPE_MAP.get(file_type)

        for f in self.files:
            # ---------- 文件大类过滤 ----------
            if file_type == "文件夹":
                if f["Type"] != "DIR":
                    continue
            else:
                if f["Type"] != "FILE":
                    continue

                if file_type == "其他":
                    if self._is_known_ext(f["Ext"]):
                        continue
                elif isinstance(exts, list):
                    if f["Ext"] not in exts:
                        continue
            if file_type == "文件夹":
                haystack = f'{f["NameLC"]} {f["Path"].lower()}'
            else:
                haystack = f'{f["NameLC"].lower()}'

            if keyword_mode == "and":
                if not all(k in haystack for k in kws):
                    continue
            else:  # or
                if not any(k in haystack for k in kws):
                    continue

            # ---------- 文件大小过滤 ----------
            size = f.get("RawSize", 0)
            if min_size is not None and size < min_size:
                continue
            if max_size is not None and size > max_size:
                continue

            # ---------- 时间过滤 ----------
            ts = f.get("UpdateTS", 0)
            if min_time is not None and ts < min_time:
                continue
            if max_time is not None and ts > max_time:
                continue

            append(f)

        # ---------- 排序 ----------
        if sort_by == "size":
            results.sort(key=lambda x: x.get("RawSize", 0), reverse=reverse)
        elif sort_by == "name":
            results.sort(key=lambda x: x.get("NameLC", ""), reverse=reverse)
        else:  # time
            results.sort(key=lambda x: x.get("UpdateTS", 0), reverse=reverse)

        return results

    # =========================
    # Index storage
    # =========================
    def _build_meta(self, drives):
        self.meta = {
            "created_at": time.time(),
            "updated_at": time.time(),
            "python": sys.version,
            "drives": drives,
            "skip_dirs": sorted(self.skip_dirs),
            "total_files": len(self.files),
        }

    def _save_index(self):
        with gzip.open(self.index_file, "wb") as f:
            pickle.dump({"meta": self.meta, "files": self.files}, f)

    def _try_load_index(self):
        try:
            with gzip.open(self.index_file, "rb") as f:
                data = pickle.load(f)
        except Exception:
            return False

        self.meta = data["meta"]
        self.files = data["files"]
        self.file_map = {f["Path"]: f for f in self.files}
        return True

    @staticmethod
    def _is_known_ext(ext):
        for v in FILE_TYPE_MAP.values():
            if isinstance(v, list) and ext in v:
                return True
        return False

    @staticmethod
    def enrich_for_display(item):
        item = dict(item)
        item["Size"] = format_size(item.get("RawSize", 0))
        return item


# =========================
# Test
# =========================
if __name__ == "__main__":
    indexer = DiskIndexer()
    results = indexer.search("Docker", "文档")
    for r in results:
        print(r)
