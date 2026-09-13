import sys, os, ctypes

src = os.path.dirname(os.path.abspath(__file__))
if src not in sys.path:
    sys.path.insert(0, src)

if os.name == "nt":
    os.system("chcp 65001 >nul 2>&1")
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # Enable ANSI / VT100
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)

        # Maximize window
        SW_MAXIMIZE = 3
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_MAXIMIZE)

        # Set larger font to fill screen (Consolas size 16x32)
        try:
            class COORD(ctypes.Structure):
                _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]
            class CONSOLE_FONT_INFOEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("nFont", ctypes.c_ulong),
                    ("dwFontSize", COORD),
                    ("FontFamily", ctypes.c_uint),
                    ("FontWeight", ctypes.c_uint),
                    ("FaceName", ctypes.c_wchar * 32),
                ]
            font = CONSOLE_FONT_INFOEX()
            font.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
            font.nFont = 0
            font.dwFontSize.X = 0
            font.dwFontSize.Y = 28
            font.FontFamily = 54
            font.FontWeight = 400
            font.FaceName = "Consolas"
            h_console = kernel32.GetStdHandle(-11)
            kernel32.SetCurrentConsoleFontEx(h_console, False, ctypes.byref(font))
        except Exception:
            pass

        # Remove scrollbars, set to fill window
        try:
            os.system("mode con: rate=31 delay=1 >nul 2>&1")
        except Exception:
            pass
    except Exception:
        pass

from ui import hide_cursor, show_cursor
from menu import show_title, show_class_select, show_controls, show_name_input, show_seed_input


def main():
    hide_cursor()
    try:
        while True:
            action = show_title()
            if action == "quit":
                break
            elif action == "settings":
                from settings import show_settings
                show_settings()
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.flush()
            elif action == "controls":
                show_controls()
            elif action == "new_game":
                name = show_name_input()
                if not name:
                    continue
                class_name = show_class_select()
                if class_name:
                    # Seed input: empty = random
                    seed = show_seed_input()
                    import random as _random
                    import map_generator
                    if seed:
                        _random.seed(seed)
                        map_generator.SEED_BASE = seed
                    else:
                        map_generator.SEED_BASE = None
                    from game import run_game
                    run_game(class_name, name)
                    # Clear screen before returning to menu
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        try:
            sys.stdout.write("\x1b[0m\x1b[2J\x1b[H")
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()
