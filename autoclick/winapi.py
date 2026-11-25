"""Acesso à API do Windows: envio de teclas/mouse (SendInput) e leitura de estado."""
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")
winmm.timeBeginPeriod(1)  # timers de 1 ms

# ---------------------------------------------------------------- SendInput
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x1
KEYEVENTF_KEYUP = 0x2
KEYEVENTF_SCANCODE = 0x8
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)

# VK 4 = botão do meio, 5/6 = botões laterais (X1/X2): (down, up, mouseData)
MOUSE_FLAGS = {4: (0x20, 0x40, 0), 5: (0x80, 0x100, 1), 6: (0x80, 0x100, 2)}
MOUSE_NAMES = {4: "Mouse: botão do meio", 5: "Mouse: lateral 1 (voltar)",
               6: "Mouse: lateral 2 (avançar)"}


def scan_info(vk):
    sc = user32.MapVirtualKeyW(vk, 4)  # MAPVK_VK_TO_VSC_EX
    ext = (sc >> 8) in (0xE0, 0xE1)
    return sc & 0xFF, ext


def send_key(vk, down):
    if vk in MOUSE_FLAGS:
        f_down, f_up, data = MOUSE_FLAGS[vk]
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(0, 0, data, f_down if down else f_up, 0, 0)
    else:
        sc, ext = scan_info(vk)
        flags = KEYEVENTF_SCANCODE
        if ext:
            flags |= KEYEVENTF_EXTENDEDKEY
        if not down:
            flags |= KEYEVENTF_KEYUP
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki = KEYBDINPUT(0, sc, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def key_name(vk):
    if vk in MOUSE_NAMES:
        return MOUSE_NAMES[vk]
    sc, ext = scan_info(vk)
    buf = ctypes.create_unicode_buffer(64)
    lparam = (sc << 16) | (int(ext) << 24)
    if sc and user32.GetKeyNameTextW(lparam, buf, 64):
        return buf.value
    return f"VK_{vk}"


def is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


# Ignora botão esquerdo/direito do mouse (usados na interface) e os
# Shift/Ctrl/Alt genéricos (16-18; usamos as versões esquerda/direita).
SCAN_VKS = [v for v in range(3, 255) if v not in (1, 2, 16, 17, 18)]
