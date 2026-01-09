import ctypes
import os
import time
import pickle
import gzip
import sys

from ctypes import wintypes
from typing import Dict, List, Optional, Any, Iterable, Tuple, Set

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
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"],
    "文档": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
    "音频": [".mp3", ".wav", ".flac", ".aac"],
    "压缩包": [".zip", ".rar", ".7z"],
    "代码": [".py", ".js", ".html", ".css", ".json", ".xml"],
    "可执行文件": [".exe", ".msi", ".bat"],
}


# =========================
# DiskIndexer（工程版）
# =========================
class DiskIndexer:
    INDEX_VERSION = 1

    COMMON_SKIP_DIRS = {
        "$recycle.bin",
        "system volume information",
    }

    SKIP_DIRS_BY_DRIVE = {
        "C:": {
            "windows",
            "program files",
            "program files (x86)",
            "programdata",
        }
    }

    def __init__(
            self,
            index_file: str = "kernel32_index.pkl.gz",
            skip_dirs: Optional[Iterable[str]] = None,
            drive: str = "C:",
            auto_build: bool = True,
    ):
        self.index_file = index_file

        drive = drive.upper()

        base_skip = set(map(str.lower, self.COMMON_SKIP_DIRS))
        drive_skip = set(
            d.lower()
            for d in self.SKIP_DIRS_BY_DRIVE.get(drive, [])
        )
        user_skip = set(
            d.lower()
            for d in (skip_dirs or [])
        )

        # 合并规则（优先级：用户 > 驱动器 > 全局）
        self.skip_dirs: Set[str] = base_skip | drive_skip | user_skip

        self.files = []
        self.file_map = {}
        self.meta = {}
        self.ready = False

        self._init_index(auto_build)

    def _init_index(self, auto_build: bool):
        if os.path.exists(self.index_file):
            if self._try_load_index():
                self.ready = True
                return
            else:
                print("索引损坏或不兼容，准备重建…")
                try:
                    os.remove(self.index_file)
                except OSError:
                    pass

        if auto_build:
            print("索引不存在，首次启动自动建立索引…")
            self.build_index(force=True)
            self.ready = True
        else:
            self.ready = False

    def build_index(self, drives: Optional[List[str]] = None, force: bool = False):
        if not force and self._try_load_index():
            print("已加载现有索引（无需重建）")
            return

        if drives is None:
            drives = get_available_drives()

        print(f"开始建立索引: {', '.join(drives)}")
        start = time.time()

        self.files.clear()
        self.file_map.clear()

        for d in drives:
            self._scan_drive_full(d)

        self._build_meta(drives)
        self._save_index()

        print(f"索引完成，耗时 {time.time() - start:.2f}s，文件数 {len(self.files)}")

    def update_index(self, drives: Optional[List[str]] = None):
        """增量更新索引（推荐日常使用）"""
        if not self._try_load_index():
            self.build_index(drives=drives, force=True)
            return

        if drives is None:
            drives = self.meta.get("drives") or get_available_drives()

        print("开始增量更新索引...")
        start = time.time()

        for d in drives:
            self._scan_drive_incremental(d)

        self.meta["updated_at"] = time.time()
        self.meta["total_files"] = len(self.files)

        self._save_index()

        print(f"增量更新完成，耗时 {time.time() - start:.2f}s")

    def rebuild_index(self, drives: Optional[List[str]] = None):
        print("强制重建索引...")
        if os.path.exists(self.index_file):
            os.remove(self.index_file)
        self.build_index(drives=drives, force=True)

    # =========================
    # 扫描逻辑
    # =========================
    def _scan_drive_full(self, root: str):
        stack = [root]

        while stack:
            path = stack.pop()
            search_path = os.path.join(path, "*")

            fd = WIN32_FIND_DATAW()
            h = kernel32.FindFirstFileW(search_path, ctypes.byref(fd))
            if h == INVALID_HANDLE_VALUE:
                continue

            try:
                while True:
                    name = fd.cFileName
                    if name not in (".", ".."):
                        full = os.path.join(path, name)
                        is_dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY

                        if is_dir:
                            if name.lower() not in self.skip_dirs:
                                stack.append(full)
                        else:
                            item = self._build_file_item(fd, name, full)
                            self.files.append(item)
                            self.file_map[full] = item

                    if not kernel32.FindNextFileW(h, ctypes.byref(fd)):
                        break
            finally:
                kernel32.FindClose(h)

    def _scan_drive_incremental(self, root: str):
        stack = [root]
        seen_paths = set()

        while stack:
            path = stack.pop()
            search_path = os.path.join(path, "*")

            fd = WIN32_FIND_DATAW()
            h = kernel32.FindFirstFileW(search_path, ctypes.byref(fd))
            if h == INVALID_HANDLE_VALUE:
                continue

            try:
                while True:
                    name = fd.cFileName
                    if name not in (".", ".."):
                        full = os.path.join(path, name)
                        is_dir = fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY

                        if is_dir:
                            if name.lower() not in self.skip_dirs:
                                stack.append(full)
                        else:
                            seen_paths.add(full)
                            fp = self._fingerprint(fd)

                            old = self.file_map.get(full)
                            if not old:
                                item = self._build_file_item(fd, name, full)
                                self.files.append(item)
                                self.file_map[full] = item
                            elif old["FP"] != fp:
                                self._update_file_item(old, fd)

                    if not kernel32.FindNextFileW(h, ctypes.byref(fd)):
                        break
            finally:
                kernel32.FindClose(h)

        # 删除不存在的文件
        to_remove = [
            p for p in self.file_map
            if p.startswith(root) and p not in seen_paths
        ]

        for p in to_remove:
            item = self.file_map.pop(p)
            self.files.remove(item)

    # =========================
    # 文件构建 / 更新
    # =========================
    def _build_file_item(self, fd, name, full_path) -> Dict[str, Any]:
        size = (fd.nFileSizeHigh << 32) + fd.nFileSizeLow
        ext = os.path.splitext(name)[1].lower()
        ts = (
                fd.ftLastWriteTime.dwHighDateTime << 32
                | fd.ftLastWriteTime.dwLowDateTime
        )

        return {
            "Name": name,
            "NameLC": name.lower(),
            "Ext": ext,
            "Path": full_path,
            "RawSize": size,
            "UpdateTime": filetime_to_str(fd.ftLastWriteTime),
            "UpdateTS": ts,
            "FP": self._fingerprint(fd),
        }

    def _update_file_item(self, item: Dict[str, Any], fd):
        size = (fd.nFileSizeHigh << 32) + fd.nFileSizeLow
        item["RawSize"] = size
        item["UpdateTime"] = filetime_to_str(fd.ftLastWriteTime)
        item["FP"] = self._fingerprint(fd)

    @staticmethod
    def _fingerprint(fd) -> Tuple[int, int, int, int]:
        return (
            fd.nFileSizeHigh,
            fd.nFileSizeLow,
            fd.ftLastWriteTime.dwLowDateTime,
            fd.ftLastWriteTime.dwHighDateTime,
        )

    # =========================
    # 搜索
    # =========================
    def search(self, keyword: str, file_type: str):
        keyword = keyword.strip().lower()
        if not keyword:
            return []

        exts = None
        if file_type in FILE_TYPE_MAP:
            exts = set(FILE_TYPE_MAP[file_type])

        results = []
        append = results.append

        for f in self.files:
            if keyword not in f["NameLC"]:
                continue
            if exts and f["Ext"] not in exts:
                continue
            append(f)

        return results

    def search_advanced(
            self,
            keywords: str,
            file_type: Optional[str] = None,
            sort_by: str = "time",  # time | size | name
            reverse: bool = True,
            min_size: Optional[int] = None,
            max_size: Optional[int] = None,
            match_mode: str = "or",
    ):
        if not keywords:
            return []

        # 多关键词 AND
        kws = [k.lower() for k in keywords.split() if k.strip()]
        if not kws:
            return []

        # 文件类型过滤
        exts = None
        if file_type in FILE_TYPE_MAP:
            exts = set(FILE_TYPE_MAP[file_type])

        results = []
        append = results.append

        for f in self.files:
            # 类型过滤
            if exts and f["Ext"] not in exts:
                continue

            # 大小过滤
            size = f.get("RawSize", 0)
            if min_size is not None and size < min_size:
                continue
            if max_size is not None and size > max_size:
                continue

            # 关键词匹配（文件名 + 路径）
            haystack = f'{f["NameLC"]} {f["Path"].lower()}'
            if match_mode == "and":
                if not all(k in haystack for k in kws):
                    continue
            else:  # or
                if not any(k in haystack for k in kws):
                    continue

            append(f)

        # 排序
        if sort_by == "size":
            results.sort(key=lambda x: x.get("RawSize", 0), reverse=reverse)
        elif sort_by == "name":
            results.sort(key=lambda x: x.get("NameLC", ""), reverse=reverse)
        else:  # time
            results.sort(key=lambda x: x.get("UpdateTS", 0), reverse=reverse)

        return results

    # =========================
    # 索引存储
    # =========================
    def _build_meta(self, drives):
        self.meta = {
            "version": self.INDEX_VERSION,
            "created_at": time.time(),
            "updated_at": time.time(),
            "python": sys.version,
            "drives": drives,
            "skip_dirs": sorted(self.skip_dirs),
            "total_files": len(self.files),
        }

    def _save_index(self):
        data = {
            "meta": self.meta,
            "files": self.files,
        }
        with gzip.open(self.index_file, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"索引已保存: {self.index_file}")

    def _try_load_index(self) -> bool:
        if not os.path.exists(self.index_file):
            return False

        try:
            with gzip.open(self.index_file, "rb") as f:
                data = pickle.load(f)
        except Exception:
            return False

        meta = data.get("meta")
        if not meta or meta.get("version") != self.INDEX_VERSION:
            return False

        if set(meta.get("skip_dirs", [])) != self.skip_dirs:
            return False

        self.meta = meta
        self.files = data.get("files", [])
        self.file_map = {f["Path"]: f for f in self.files}

        return True

    # =========================
    # UI 显示辅助
    # =========================
    @staticmethod
    def enrich_for_display(item: Dict[str, Any]) -> Dict[str, Any]:
        new_item = dict(item)
        new_item["Size"] = format_size(item.get("RawSize", 0))
        return new_item


if __name__ == '__main__':
    indexer = DiskIndexer()

    # 第一次
    # indexer.build_index()

    # 以后启动
    # indexer.update_index()

    # 搜索
    results = indexer.search('docker', '文档')
    sort_result = indexer.search_advanced(
        keywords="docker 仙逆",
        file_type="文档",
        sort_by="size",
        reverse=True,
        min_size=100 * 1024,  # ≥10KB
    )

    for result in results:
        print(result)

    print("=" * 20)

    for result1 in sort_result:
        print(result1)
