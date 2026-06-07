#!/usr/bin/env python3
"""
Detector de presença via câmera RGB — roda como tray icon.
  python presence_monitor.py           # silencioso, apenas tray icon
  python presence_monitor.py --debug   # output no terminal + janela de câmera
  python presence_monitor.py --install
  python presence_monitor.py --uninstall
"""
import ctypes
import os
import pathlib
import sys
import threading
import time
import winreg

import urllib.request
from contextlib import contextmanager

@contextmanager
def _mute():
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved   = os.dup(1), os.dup(2)
    os.dup2(devnull, 1); os.dup2(devnull, 2); os.close(devnull)
    try:
        yield
    finally:
        os.dup2(saved[0], 1); os.dup2(saved[1], 2)
        os.close(saved[0]);   os.close(saved[1])

import cv2
with _mute():
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions
import pystray
from PIL import Image, ImageDraw

# ══════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════
DEBUG          = '--debug' in sys.argv
CAMERA_INDEX   = 0      # índice da câmera (0 = padrão do sistema)
CHECK_INTERVAL = 3.0    # s entre verificações
ABSENT_STREAK  = 3      # strikes padrão para ligar/desligar (ajustável pelo menu)
MIN_CONFIDENCE = 0.5    # confiança mínima da detecção (0.0–1.0)
MODEL_FILE     = pathlib.Path(__file__).parent / "face_detector.tflite"
MODEL_URL      = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"

# ══════════════════════════════════════════════════════════════
#  INÍCIO AUTOMÁTICO
# ══════════════════════════════════════════════════════════════
_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "PresenceMonitor"


def _startup_cmd() -> str:
    exe     = pathlib.Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    runner  = pythonw if pythonw.exists() else exe
    script  = pathlib.Path(__file__).resolve()
    return f'"{runner}" "{script}"'


def _is_installed() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
            winreg.QueryValueEx(k, _APP_NAME)
        return True
    except FileNotFoundError:
        return False


def install_startup():
    cmd = _startup_cmd()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, cmd)
    print(f"Registrado no início automático:\n  {cmd}")


def uninstall_startup():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, _APP_NAME)
        print("Removido do início automático.")
    except FileNotFoundError:
        print("Não estava registrado.")


# ══════════════════════════════════════════════════════════════
#  CONTROLE DO MONITOR
# ══════════════════════════════════════════════════════════════
def monitor_off():
    ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", _MOUSEINPUT)]


def monitor_on():
    for dx in (1, -1):
        inp = _INPUT()
        inp.type = 0
        inp.mi.dwFlags = 1
        inp.mi.dx = dx
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
        time.sleep(0.05)


# ══════════════════════════════════════════════════════════════
#  ESTADO COMPARTILHADO
# ══════════════════════════════════════════════════════════════
class _State:
    is_present    = False
    monitor_is_on = True
    monitoring    = True
    auto_on       = True
    streak        = ABSENT_STREAK
    quit          = False


state               = _State()
_icon: pystray.Icon = None


# ══════════════════════════════════════════════════════════════
#  ÍCONE DA BANDEJA
# ══════════════════════════════════════════════════════════════
def _make_icon_image() -> Image.Image:
    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if not state.monitoring:
        fill = (140, 140, 140)
    elif state.is_present:
        fill = (40, 200, 80)
    else:
        fill = (60, 100, 220)
    draw.ellipse([4, 4, size - 4, size - 4], fill=fill)
    if not state.monitor_is_on:
        cx, cy, r = size // 2, size // 2, 13
        draw.line([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255), width=5)
        draw.line([cx + r, cy - r, cx - r, cy + r], fill=(255, 255, 255), width=5)
    return img


def _make_title() -> str:
    if not state.monitoring:
        return "Detector de Presença [pausado]"
    status = "Presente" if state.is_present else "Ausente"
    mon    = "ON"       if state.monitor_is_on else "OFF"
    return f"Presença: {status} | Monitor: {mon}"


def _refresh_icon():
    if _icon is None:
        return
    _icon.icon  = _make_icon_image()
    _icon.title = _make_title()
    _icon.update_menu()


def _make_menu() -> pystray.Menu:
    def toggle_monitoring(icon, item):
        state.monitoring = not state.monitoring
        _refresh_icon()

    def toggle_auto_on(icon, item):
        state.auto_on = not state.auto_on
        icon.update_menu()

    def set_streak(n):
        def _set(icon, item):
            state.streak = n
            icon.update_menu()
        return _set

    def force_on(icon, item):
        monitor_on()
        state.monitor_is_on = True
        _refresh_icon()

    def force_off(icon, item):
        monitor_off()
        state.monitor_is_on = False
        _refresh_icon()

    def toggle_startup(icon, item):
        if _is_installed():
            uninstall_startup()
        else:
            install_startup()
        icon.update_menu()

    def quit_app(icon, item):
        state.quit = True
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem(
            lambda item: "Pausar detecção" if state.monitoring else "Retomar detecção",
            toggle_monitoring,
        ),
        pystray.MenuItem(
            lambda item: "Ligar automático: ON  ✓" if state.auto_on else "Ligar automático: OFF",
            toggle_auto_on,
        ),
        pystray.MenuItem(
            lambda item: f"Delay: {state.streak} strikes ({int(state.streak * CHECK_INTERVAL)}s)",
            pystray.Menu(*(
                pystray.MenuItem(
                    f"{n} strike{'s' if n > 1 else ''}  ({int(n * CHECK_INTERVAL)}s)",
                    set_streak(n),
                    checked=lambda item, n=n: state.streak == n,
                )
                for n in range(1, 11)
            )),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ligar monitor",    force_on),
        pystray.MenuItem("Desligar monitor", force_off),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            lambda item: "Remover do início automático" if _is_installed() else "Iniciar com o Windows",
            toggle_startup,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", quit_app),
    )


# ══════════════════════════════════════════════════════════════
#  LISTENER DE ENERGIA DO MONITOR (GUID_MONITOR_POWER_ON)
# ══════════════════════════════════════════════════════════════
def _power_listener():
    import ctypes.wintypes as _wt

    WM_POWERBROADCAST      = 0x0218
    PBT_POWERSETTINGCHANGE = 0x8013
    PM_REMOVE              = 0x0001

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    class _PBS(ctypes.Structure):
        _fields_ = [("PowerSetting", _GUID), ("DataLength", ctypes.c_ulong),
                    ("Data", ctypes.c_ulong)]

    _WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, _wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM)

    class _WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize",        _wt.UINT),    ("style",         _wt.UINT),
            ("lpfnWndProc",   _WNDPROC),    ("cbClsExtra",    ctypes.c_int),
            ("cbWndExtra",    ctypes.c_int), ("hInstance",     _wt.HANDLE),
            ("hIcon",         _wt.HANDLE),  ("hCursor",       _wt.HANDLE),
            ("hbrBackground", _wt.HANDLE),  ("lpszMenuName",  _wt.LPCWSTR),
            ("lpszClassName", _wt.LPCWSTR), ("hIconSm",       _wt.HANDLE),
        ]

    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    # GUID_MONITOR_POWER_ON = {02731015-4510-4526-99E6-E5A17EBD1AEA}
    guid_mon = _GUID(0x02731015, 0x4510, 0x4526,
                     (ctypes.c_ubyte * 8)(0x99, 0xE6, 0xE5, 0xA1, 0x7E, 0xBD, 0x1A, 0xEA))

    def _on_power(hwnd, msg, wparam, lparam):
        if msg == WM_POWERBROADCAST and wparam == PBT_POWERSETTINGCHANGE:
            pbs = ctypes.cast(lparam, ctypes.POINTER(_PBS)).contents
            is_on = bool(pbs.Data)
            if is_on != state.monitor_is_on:
                state.monitor_is_on = is_on
                _refresh_icon()
        return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wnd_proc  = _WNDPROC(_on_power)   # manter referência viva
    hinstance = k32.GetModuleHandleW(None)
    cls_name  = "PMPowerWatcher"

    wc = _WNDCLASSEX()
    wc.cbSize        = ctypes.sizeof(_WNDCLASSEX)
    wc.lpfnWndProc   = wnd_proc
    wc.hInstance     = hinstance
    wc.lpszClassName = cls_name
    u32.RegisterClassExW(ctypes.byref(wc))

    hwnd = u32.CreateWindowExW(0, cls_name, None, 0, 0, 0, 0, 0,
                               -3, None, hinstance, None)  # -3 = HWND_MESSAGE
    u32.RegisterPowerSettingNotification(hwnd, ctypes.byref(guid_mon), 0)

    msg = _wt.MSG()
    while not state.quit:
        if u32.PeekMessageW(ctypes.byref(msg), hwnd, 0, 0, PM_REMOVE):
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        else:
            time.sleep(0.05)


# ══════════════════════════════════════════════════════════════
#  LOOP DE DETECÇÃO
# ══════════════════════════════════════════════════════════════
def _detection_loop():
    def log(msg): print(msg, flush=True) if DEBUG else None

    log("[...] Thread iniciada.")
    time.sleep(1.5)  # aguarda pystray iniciar

    log("[...] Abrindo câmera...")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"[ERRO] Câmera {CAMERA_INDEX} não encontrada.", flush=True)
        return

    log(f"[OK] Câmera {CAMERA_INDEX} aberta.")

    if not MODEL_FILE.exists():
        print("[...] Baixando modelo de detecção (única vez)...", flush=True)
        urllib.request.urlretrieve(MODEL_URL, str(MODEL_FILE))
        print("[OK] Modelo baixado.", flush=True)

    with _mute():
        detector = FaceDetector.create_from_options(
            FaceDetectorOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_FILE)),
                min_detection_confidence=MIN_CONFIDENCE,
            )
        )

    absent_streak  = 0
    present_streak = 0

    try:
        while not state.quit:
            if not state.monitoring or (not state.monitor_is_on and not state.auto_on):
                time.sleep(CHECK_INTERVAL)
                continue

            # Descarta frames acumulados no buffer
            for _ in range(3):
                cap.grab()
            ret, frame = cap.retrieve()

            if not ret or frame is None:
                time.sleep(CHECK_INTERVAL)
                continue

            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            faces   = detector.detect(mp_img).detections
            present = len(faces) > 0

            prev_present = state.is_present
            prev_mon     = state.monitor_is_on

            if present:
                absent_streak    = 0
                present_streak  += 1
                state.is_present = True
                if state.auto_on and not state.monitor_is_on and present_streak >= state.streak:
                    monitor_on()
                    state.monitor_is_on = True
                    present_streak = 0
            else:
                present_streak   = 0
                absent_streak   += 1
                state.is_present = False
                if absent_streak >= state.streak:
                    monitor_off()
                    state.monitor_is_on = False
                    absent_streak = 0

            if state.is_present != prev_present or state.monitor_is_on != prev_mon:
                _refresh_icon()

            if DEBUG:
                label  = "PRESENTE" if present else "ausente "
                mon    = "ON " if state.monitor_is_on else "OFF"
                streak = f"+{present_streak}/{state.streak}" if present else f"-{absent_streak}/{state.streak}"
                print(f"\r{label}  rostos={len(faces)}  {streak}  mon={mon}   ",
                      end="", flush=True)
                if present:
                    for det in faces:
                        bb = det.bounding_box
                        cv2.rectangle(frame,
                            (bb.origin_x, bb.origin_y),
                            (bb.origin_x + bb.width, bb.origin_y + bb.height),
                            (0, 255, 0), 2)
                cv2.imshow("Câmera", frame)
                cv2.waitKey(1)

            time.sleep(CHECK_INTERVAL)

    finally:
        cap.release()
        if DEBUG:
            cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    global _icon

    if '--install' in sys.argv:
        install_startup()
        return
    if '--uninstall' in sys.argv:
        uninstall_startup()
        return

    _icon = pystray.Icon(
        name  = "presence_monitor",
        icon  = _make_icon_image(),
        title = _make_title(),
        menu  = _make_menu(),
    )

    power  = threading.Thread(target=_power_listener,  daemon=True)
    worker = threading.Thread(target=_detection_loop, daemon=True)
    power.start()
    worker.start()

    _icon.run()
    state.quit = True
    worker.join(timeout=5)
    os._exit(0)


if __name__ == "__main__":
    main()
