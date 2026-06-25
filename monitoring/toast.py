# toast.py
import ctypes
import sys
import threading
from datetime import datetime


def _win_toast(title, message, icon='info', duration=5):
    try:
        from ctypes import wintypes

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('hWnd', wintypes.HWND),
                ('uID', wintypes.UINT),
                ('uFlags', wintypes.UINT),
                ('uCallbackMessage', wintypes.UINT),
                ('hIcon', wintypes.HICON),
                ('szTip', ctypes.c_wchar * 128),
                ('dwState', wintypes.DWORD),
                ('dwStateMask', wintypes.DWORD),
                ('szInfo', ctypes.c_wchar * 256),
                ('uVersion', wintypes.UINT),
                ('szInfoTitle', ctypes.c_wchar * 64),
                ('dwInfoFlags', wintypes.DWORD),
            ]

        NIF_ICON = 0x00000004
        NIF_MESSAGE = 0x00000001
        NIF_TIP = 0x00000002
        NIF_INFO = 0x00000010
        NIM_ADD = 0x00000000
        NIM_MODIFY = 0x00000001
        NIM_DELETE = 0x00000002
        NIIF_NONE = 0x00000000
        NIIF_INFO = 0x00000001
        NIIF_WARNING = 0x00000002
        NIIF_ERROR = 0x00000003

        icon_map = {'info': NIIF_INFO, 'warning': NIIF_WARNING, 'error': NIIF_ERROR}
        dw_info_flags = icon_map.get(icon, NIIF_INFO)

        WM_TRAYICON = 0x8000 + 1

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        h_instance = kernel32.GetModuleHandleW(None)

        wnd_class = ctypes.c_wchar * 256

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM
        )

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON and lparam == 0x402:
                nid = NOTIFYICONDATAW()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
                nid.hWnd = hwnd
                nid.uID = 1
                user32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                user32.DestroyWindow(hwnd)
                user32.UnregisterClassW('ToastClass', h_instance)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wnd_proc_ptr = WNDPROC(wnd_proc)

        wc = ctypes.c_wchar * 256
        class_name = f'ToastClass_{id(wnd_proc_ptr)}'

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ('style', wintypes.UINT),
                ('lpfnWndProc', ctypes.c_void_p),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON),
                ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
            ]

        wc_struct = WNDCLASSW()
        wc_struct.style = 0
        wc_struct.lpfnWndProc = wnd_proc_ptr
        wc_struct.hInstance = h_instance
        wc_struct.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(wc_struct))

        hwnd = user32.CreateWindowExW(
            0, class_name, '', 0, 0, 0, 0, 0, None, None, h_instance, None
        )

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP | NIF_INFO
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = user32.LoadIconW(None, 32512)
        nid.szTip = title[:127]
        nid.dwState = 0
        nid.dwStateMask = 0
        nid.szInfo = message[:255]
        nid.uVersion = 0
        nid.szInfoTitle = title[:63]
        nid.dwInfoFlags = dw_info_flags

        user32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        user32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

        import time
        time.sleep(duration)

        user32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(class_name, h_instance)
        return True

    except Exception:
        return False


def show_toast(title, message, icon='info', duration=5):
    if sys.platform != 'win32':
        return False
    t = threading.Thread(target=_win_toast, args=(title, message, icon, duration),
                         daemon=True)
    t.start()
    return True
