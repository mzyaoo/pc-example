import time
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class MyEventHandler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        # 这里会打印 D 盘下所有的文件变动
        print(event)


if __name__ == "__main__":
    # Windows 下路径分隔符是 \，在字符串中需要写成 \\ 转义，或者用 r"D:\"
    path = "D:\\"

    print(f"开始监听: {path}，请尝试在 D 盘新建或删除文件...")

    event_handler = MyEventHandler()
    observer = Observer()

    # 将路径参数 "." 改为上面的 path 变量
    observer.schedule(event_handler, path, recursive=True)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 捕获 Ctrl+C 以便优雅退出
        observer.stop()
        print("停止监听")

    observer.join()