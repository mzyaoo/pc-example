import os
import time
import sys
import ctypes
from typing import List, Optional, Dict, Any


# --- 辅助函数：检查管理员权限 ---
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


# --- 核心类：文件搜索器 ---
class FileSearcher:
    # 文件类型映射表
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

    def __init__(self, drive_letters: List[str] = None, dll_path: str = None):
        if not is_admin():
            print("正在请求管理员权限...")
            relaunch_as_admin()
            sys.exit(0)

        # 路径处理：支持相对路径和绝对路径
        if dll_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.dll_path = os.path.join(base_dir, "dll", "FileSearch.dll")
        else:
            self.dll_path = dll_path

        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"找不到 DLL 文件: {self.dll_path}")

        try:
            self.h_module = ctypes.windll.LoadLibrary(self.dll_path)
            self._setup_dll_prototypes()
        except Exception as e:
            raise RuntimeError(f"加载 DLL 失败: {e}")

        self.drive_indices = {}  # 存储 {盘符: 索引句柄}
        self.drive_info = {}  # 存储 {盘符: {'num_files': int, ...}}
        self.index_time = 0.0

        # 初始化驱动器列表
        available = self._get_available_drives()
        if drive_letters:
            self.target_drives = [d.upper() for d in drive_letters if d.upper() in available]
        else:
            self.target_drives = available

        self.create_index()

    def _setup_dll_prototypes(self):
        """配置 ctypes 函数原型"""
        self.h_module.CreateIndex.argtypes = [ctypes.c_ushort]
        self.h_module.CreateIndex.restype = ctypes.c_void_p

        self.h_module.GetDriveInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        self.h_module.GetDriveInfo.restype = None

        self.h_module.Search.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_int)]
        self.h_module.Search.restype = ctypes.c_void_p

        self.h_module.FreeResultsBuffer.argtypes = [ctypes.c_void_p]
        self.h_module.FreeResultsBuffer.restype = None

        self.h_module.LoadIndexFromDisk.argtypes = [ctypes.c_char_p]
        self.h_module.LoadIndexFromDisk.restype = ctypes.c_void_p

        self.h_module.SaveIndexToDisk.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self.h_module.SaveIndexToDisk.restype = ctypes.c_uint

        self.h_module.DeleteIndex.argtypes = [ctypes.c_void_p]
        self.h_module.DeleteIndex.restype = None

    def _get_available_drives(self) -> List[str]:
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            if bitmask & 1:
                # 过滤掉 A 和 B 盘（通常是软驱）
                if letter not in 'AB':
                    drives.append(letter)
            bitmask >>= 1
        return drives

    def create_index(self):
        """重建所有选定驱动器的索引"""
        print(f"开始建立驱动器索引: {', '.join(self.target_drives)}...")
        self.delete_index()  # 确保清理旧句柄

        start_t = time.time()
        for drive in self.target_drives:
            # 传入 ASCII 码
            handle = self.h_module.CreateIndex(ord(drive))
            if handle:
                self.drive_indices[drive] = handle
                self._update_drive_info(drive)
            else:
                print(f"[错误] 无法索引驱动器 {drive}:")

        self.index_time = time.time() - start_t
        print(f"全盘索引创建完成，耗时: {self.index_time:.2f}s")

    def _update_drive_info(self, drive: str):
        if drive not in self.drive_indices: return

        buf = ctypes.create_string_buffer(16)
        self.h_module.GetDriveInfo(self.drive_indices[drive], buf, 16)

        num_f = int.from_bytes(buf.raw[0:8], 'little')
        num_d = int.from_bytes(buf.raw[8:16], 'little')
        self.drive_info[drive] = {'num_files': num_f, 'num_directories': num_d}

    def search(
            self,
            query: str,
            file_type: str = None,
            limit: int = 1000,
            case_insensitive: bool = True
    ) -> (str, int):
        """执行全盘搜索"""
        if not self.drive_indices:
            return "索引未就绪", 0

        start_t = time.time()
        all_results = []

        # 预处理 Python 层过滤条件
        match_phrase = query.lower() if case_insensitive else query
        ext_tuple = None
        if file_type and file_type in self.FILE_TYPE_MAP:
            ext_tuple = tuple(e.lower() for e in self.FILE_TYPE_MAP[file_type])

        for drive, handle in self.drive_indices.items():
            n_results = ctypes.c_int(0)
            # 调用 DLL 搜索 (此处假设 DLL 内部不进行后缀过滤)
            p_buf = self.h_module.Search(
                handle, query, "",
                1 if case_insensitive else 0, 0, limit * 2,  # 取双倍余量给后缀过滤
                ctypes.byref(n_results)
            )

            if not p_buf: continue

            try:
                raw_str = ctypes.wstring_at(p_buf)
                paths = raw_str.strip().split('\n') if raw_str.strip() else []

                # Python 级精筛
                for p in paths:
                    if not p: continue
                    filename = os.path.basename(p)
                    cmp_name = filename.lower() if case_insensitive else filename

                    if match_phrase not in cmp_name: continue
                    if ext_tuple and not cmp_name.endswith(ext_tuple): continue

                    all_results.append(p)
                    if len(all_results) >= limit: break
            finally:
                self.h_module.FreeResultsBuffer(p_buf)

            if len(all_results) >= limit: break

        elapsed = time.time() - start_t
        return "\n".join(all_results), len(all_results), elapsed

    def delete_index(self):
        """释放 DLL 占用的内存资源"""
        for handle in self.drive_indices.values():
            if handle:
                self.h_module.DeleteIndex(handle)
        self.drive_indices.clear()
        self.drive_info.clear()

    def save_indices(self):
        """保存当前所有驱动器的索引"""
        for drive, handle in self.drive_indices.items():
            path = os.path.abspath(f"index\\index_{drive}.dat")
            res = self.h_module.SaveIndexToDisk(handle, path)
            if res == 1:
                print(f"驱动器 {drive} 索引已保存至: {path}")


# --- 交互界面 ---

def main():
    try:
        searcher = FileSearcher()

        print("\n" + "=" * 40)
        print("   高 性 能 全 盘 搜 索 工 具   ")
        print("=" * 40)

        for drive, info in searcher.drive_info.items():
            print(f"驱动器 [{drive}:] -> 文件: {info['num_files']:,} | 目录: {info['num_directories']:,}")

        print("\n[可用命令] info, rebuild, save, exit")
        print("[搜索技巧] 直接输入关键词；或使用 '关键词 type:文档'")

        while True:
            raw_input = input("\n搜索或命令 >> ").strip()
            if not raw_input: continue

            cmd = raw_input.lower()
            if cmd in ['exit', 'quit']: break
            if cmd == 'info':
                for d, i in searcher.drive_info.items():
                    print(f"{d}: {i['num_files']} files")
                continue
            if cmd == 'rebuild':
                searcher.create_index()
                continue
            if cmd == 'save':
                searcher.save_indices()
                continue

            # 解析搜索参数
            search_query = raw_input
            filter_type = None
            if "type:" in raw_input:
                parts = raw_input.split("type:")
                search_query = parts[0].strip()
                filter_type = parts[1].strip()

            results, count, duration = searcher.search(search_query, file_type=filter_type)

            print(f"\n--- 找到 {count} 个结果 (耗时: {duration:.4f}s) ---")
            if count > 0:
                print(results)
            else:
                print("未找到匹配项。")

    except Exception as e:
        print(f"程序运行出错: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()