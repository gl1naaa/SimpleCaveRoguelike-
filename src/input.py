import os
import sys
import time
import atexit
from typing import Set, Optional

# ── Platform detection ───────────────────────────────────────────────
_IS_WINDOWS = os.name == "nt"

# ── Virtual key codes (Windows, layout-independent) ──────────────────
VK = {
    "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "SPACE": 0x20, "ESC": 0x1B,
    "I": 0x49, "E": 0x45, "Z": 0x5A, "X": 0x58, "C": 0x43,
    "V": 0x56, "B": 0x42, "N": 0x4E, "M": 0x4D,
    "TAB": 0x09, "DEL": 0x2E,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
    "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}

# ── Key-name → action mapping ────────────────────────────────────────
_KEY_ACTION = {
    "W": "up", "UP": "up", "S": "down", "DOWN": "down",
    "A": "left", "LEFT": "left", "D": "right", "RIGHT": "right",
    "SPACE": "action", "ESC": "quit",
    "E": "inventory", "I": "inventory",
    "Z": "skill0", "X": "skill1", "C": "skill2",
    "V": "skill3", "B": "skill4", "N": "skill5",
    "M": "meta_shop",
    "TAB": "tab", "DEL": "delete",
    "1": "hotkey0", "2": "hotkey1", "3": "hotkey2", "4": "hotkey3",
    "5": "hotkey4", "6": "hotkey5", "7": "hotkey6", "8": "hotkey7",
    "9": "hotkey8",
}

# Character → action for terminal / msvcrt backends
_CHAR_ACTION = {
    'w': "up", 'W': "up", 'a': "left", 'A': "left",
    's': "down", 'S': "down", 'd': "right", 'D': "right",
    ' ': "action", 'q': "quit", 'Q': "quit",
    'i': "inventory", 'I': "inventory", 'e': "inventory", 'E': "inventory",
    'z': "skill0", 'x': "skill1", 'c': "skill2",
    'v': "skill3", 'b': "skill4", 'n': "skill5",
    'Z': "skill0", 'X': "skill1", 'C': "skill2",
    'V': "skill3", 'B': "skill4", 'N': "skill5",
    'm': "meta_shop", 'M': "meta_shop",
    '\u043c': "meta_shop", '\u041c': "meta_shop",  # русская м/М
    '\u044c': "meta_shop", '\u042c': "meta_shop",  # русская ь/Ь
    '\t': "tab",
    '\x7f': "delete", '\x08': "delete",
    '1': "hotkey0", '2': "hotkey1", '3': "hotkey2", '4': "hotkey3",
    '5': "hotkey4", '6': "hotkey5", '7': "hotkey6", '8': "hotkey7",
    '9': "hotkey8",
}

# ── Backend state ────────────────────────────────────────────────────
_backend_type: str = "null"   # "win32" | "msvcrt" | "termios" | "null"
_user32 = None
_msvcrt = None
_termios_mod = None
_tty_mod = None
_old_termios_settings = None
_stdin_fd = None
_pressed_actions: Set[str] = set()
_last_drain_time: float = 0.0
_DRAIN_TTL: float = 0.016     # 16 ms – multiple is_key_pressed calls share one drain


def _init_backend():
    """Try each backend in order; stop at the first one that works."""
    global _backend_type, _user32, _msvcrt
    global _termios_mod, _tty_mod, _old_termios_settings, _stdin_fd

    if _IS_WINDOWS:
        # 1) ctypes.windll.user32 (primary)
        try:
            import ctypes
            _user32 = ctypes.windll.user32
            _user32.GetAsyncKeyState(0)           # sanity check
            _backend_type = "win32"
            return
        except Exception:
            _user32 = None

        # 2) msvcrt (Windows fallback)
        try:
            import msvcrt as _m
            _msvcrt = _m
            _backend_type = "msvcrt"
            return
        except Exception:
            _msvcrt = None
    else:
        # 3) termios + select (Linux / macOS)
        try:
            import termios as _t
            import tty as _tt
            _termios_mod = _t
            _tty_mod = _tt
            _stdin_fd = sys.stdin.fileno()
            _old_termios_settings = _t.tcgetattr(_stdin_fd)
            _tty_mod.setcbreak(_stdin_fd)
            atexit.register(_cleanup_termios)
            _backend_type = "termios"
            return
        except Exception:
            _termios_mod = None

    _backend_type = "null"


def _cleanup_termios():
    """Restore terminal settings on exit."""
    if _old_termios_settings is not None and _stdin_fd is not None \
            and _termios_mod is not None:
        try:
            _termios_mod.tcsetattr(
                _stdin_fd, _termios_mod.TCSADRAIN, _old_termios_settings
            )
        except Exception:
            pass


_init_backend()


# ── Drain helpers (platform-specific) ───────────────────────────────

def _drain_win32():
    """Poll every VK key via GetAsyncKeyState."""
    _pressed_actions.clear()
    for name, vk in VK.items():
        if _user32.GetAsyncKeyState(vk) & 0x8000:
            action = _KEY_ACTION.get(name)
            if action:
                _pressed_actions.add(action)


def _drain_msvcrt():
    """Read all buffered characters from msvcrt (non-blocking)."""
    _pressed_actions.clear()
    while _msvcrt.kbhit():
        try:
            ch = _msvcrt.getwch()
        except Exception:
            break
        if ch in ('\xe0', '\x00'):
            # Extended key prefix – read the second byte
            try:
                ch2 = _msvcrt.getwch()
            except Exception:
                break
            arrows = {'H': "up", 'P': "down", 'M': "right", 'K': "left"}
            action = arrows.get(ch2)
            if action:
                _pressed_actions.add(action)
            continue
        action = _CHAR_ACTION.get(ch)
        if action:
            _pressed_actions.add(action)


def _drain_termios():
    """Read all available input from terminal (non-blocking via select)."""
    import select as _sel
    _pressed_actions.clear()
    while True:
        r, _, _ = _sel.select([sys.stdin], [], [], 0)
        if not r:
            break
        try:
            ch = sys.stdin.read(1)
        except Exception:
            break
        if ch == '\x1b':
            # Escape sequence – peek for '[A' style arrow key
            r2, _, _ = _sel.select([sys.stdin], [], [], 0.01)
            if r2:
                try:
                    seq = sys.stdin.read(2)
                except Exception:
                    _pressed_actions.add("quit")
                    continue
                arrows = {
                    '[A': "up", '[B': "down",
                    '[C': "right", '[D': "left",
                }
                action = arrows.get(seq)
                if action:
                    _pressed_actions.add(action)
            else:
                _pressed_actions.add("quit")       # bare ESC
            continue
        action = _CHAR_ACTION.get(ch)
        if action:
            _pressed_actions.add(action)


def _drain_input():
    """Drain platform-specific input into _pressed_actions."""
    if _user32:
        _drain_win32()
    elif _msvcrt:
        _drain_msvcrt()
    elif _termios_mod:
        _drain_termios()
    else:
        _pressed_actions.clear()


def _drain_if_stale():
    """Drain only if the buffer is older than _DRAIN_TTL seconds."""
    global _last_drain_time
    now = time.monotonic()
    if now - _last_drain_time >= _DRAIN_TTL:
        _drain_input()
        _last_drain_time = now


# ── Public API ──────────────────────────────────────────────────────

def is_key_pressed(key: str) -> bool:
    """Check if a key is currently pressed.  Cross-platform.

    *Windows (ctypes)* – polls GetAsyncKeyState directly (no drain needed).
    *Terminal / msvcrt* – drains buffered input and checks the result.
    *Null backend*     – always returns ``False``.
    """
    if _user32:
        vk = VK.get(key)
        if vk is None:
            return False
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)

    # For terminal / msvcrt backends: drain once within the TTL window,
    # then check the cached buffer so multiple calls in the same frame
    # all see the same snapshot.
    _drain_if_stale()
    action = _KEY_ACTION.get(key)
    if action is None:
        return False
    return action in _pressed_actions


def get_backend() -> str:
    """Return the active backend: ``'win32'``, ``'msvcrt'``,
    ``'termios'``, or ``'null'``."""
    return _backend_type


# ── Backward-compatible _is_pressed (VK code) ───────────────────────

def _is_pressed(vk: int) -> bool:
    """Legacy helper – poll a Windows virtual-key code."""
    if _user32:
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)
    # For non-win32 backends, reverse-map VK → action → check buffer
    for name, code in VK.items():
        if code == vk:
            action = _KEY_ACTION.get(name)
            if action:
                return action in _pressed_actions
    return False


# ── InputState ──────────────────────────────────────────────────────

class InputState:
    def __init__(self):
        self._prev: Set[str] = set()

    def read(self) -> Set[str]:
        """Read all currently pressed keys.  Returns *newly* pressed actions
        (edge detection)."""
        _drain_input()
        now = set(_pressed_actions)
        pressed = now - self._prev
        self._prev = now
        return pressed

    def is_held(self, action: str) -> bool:
        """Check if *action* key is currently held down.

        On Windows (ctypes) this polls the real key state.
        On terminal backends this checks the last-drained buffer (best
        effort – terminal input is character-based, not state-based).
        """
        if _user32:
            held_map = {
                "up":    ("W", "UP"),
                "down":  ("S", "DOWN"),
                "left":  ("A", "LEFT"),
                "right": ("D", "RIGHT"),
            }
            keys = held_map.get(action, ())
            return any(
                bool(_user32.GetAsyncKeyState(VK[k]) & 0x8000)
                for k in keys if k in VK
            )
        # Terminal / msvcrt: check the last drained snapshot
        _drain_if_stale()
        return action in _pressed_actions


# ── Blocking helpers ────────────────────────────────────────────────

def wait_for_any_key():
    """Block until any key is pressed."""
    if _user32:
        time.sleep(0.1)
        while any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in VK.values()):
            time.sleep(0.02)
        while not any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in VK.values()):
            time.sleep(0.02)
    elif _msvcrt:
        try:
            _msvcrt.getwch()
        except Exception:
            pass
    elif _termios_mod:
        try:
            sys.stdin.read(1)
        except Exception:
            pass


def read_text_input(max_len: int = 12, prompt: str = "Name: ") -> str:
    """Simple text input for nickname.  Uses stdin.

    Temporarily restores the terminal to normal mode when running under the
    termios backend so that line-buffered input works correctly.
    """
    # Restore normal terminal mode for text entry
    restored = False
    if _old_termios_settings is not None and _stdin_fd is not None \
            and _termios_mod is not None:
        _termios_mod.tcsetattr(
            _stdin_fd, _termios_mod.TCSADRAIN, _old_termios_settings
        )
        restored = True
    try:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        name = sys.stdin.readline().strip()[:max_len]
        return name if name else "Adventurer"
    except Exception:
        return "Adventurer"
    finally:
        if restored and _termios_mod is not None and _stdin_fd is not None:
            try:
                _tty_mod.setcbreak(_stdin_fd)
            except Exception:
                pass
