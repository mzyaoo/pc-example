import ctypes, time,os

user32 = ctypes.windll.user32
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1

def _media_key(vk: int):
    user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

def media_play_pause(): _media_key(VK_MEDIA_PLAY_PAUSE)
def media_next(): _media_key(VK_MEDIA_NEXT_TRACK)
def media_prev(): _media_key(VK_MEDIA_PREV_TRACK)




# 使用示例
if __name__ == "__main__":
    media_play_pause()

# if __name__ == "__main__":
#     print()