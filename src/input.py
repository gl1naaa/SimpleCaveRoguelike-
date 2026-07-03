import ctypes, os, sys, time
from typing import Set

_user32 = ctypes.windll.user32 if os.name == "nt" else None

# Virtual key codes (physical positions, layout-independent)
VK = {
    "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "SPACE": 0x20, "ESC": 0x1B,
    "I": 0x49, "E": 0x45, "Z": 0x5A, "X": 0x58, "C": 0x43,
    "V": 0x56, "B": 0x42, "N": 0x4E,
    "ENTER": 0x0D, "TAB": 0x09,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
}

def _is_pressed(vk):
    if _user32:
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)
    return False

class InputState:
    def __init__(self):
        self._prev = set()
    
    def read(self) -> Set[str]:
        """Read all currently pressed keys. Returns action set."""
        now = set()
        if _user32:
            if _is_pressed(VK["W"]) or _is_pressed(VK["UP"]):    now.add("up")
            if _is_pressed(VK["S"]) or _is_pressed(VK["DOWN"]):  now.add("down")
            if _is_pressed(VK["A"]) or _is_pressed(VK["LEFT"]):  now.add("left")
            if _is_pressed(VK["D"]) or _is_pressed(VK["RIGHT"]): now.add("right")
            if _is_pressed(VK["SPACE"]): now.add("action")
            if _is_pressed(VK["ESC"]):   now.add("quit")
            if _is_pressed(VK["E"]):     now.add("inventory")
            if _is_pressed(VK["Z"]):     now.add("skill0")
            if _is_pressed(VK["X"]):     now.add("skill1")
            if _is_pressed(VK["C"]):     now.add("skill2")
            if _is_pressed(VK["V"]):     now.add("skill3")
            if _is_pressed(VK["B"]):     now.add("skill4")
            if _is_pressed(VK["N"]):     now.add("skill5")
            if _is_pressed(VK["ENTER"]): now.add("enter")
            if _is_pressed(VK["TAB"]):   now.add("tab")
            for i, k in enumerate(["1","2","3","4","5"], 0):
                if _is_pressed(VK[k]): now.add(f"hotkey{i}")
        else:
            # Fallback for pipe/stdin
            try:
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    line = sys.stdin.readline().strip().lower()
                    if not line: now.add("quit")
                    else:
                        c = line[0]
                        if c == "w": now.add("up")
                        elif c == "s": now.add("down")
                        elif c == "a": now.add("left")
                        elif c == "d": now.add("right")
                        elif c == " ": now.add("action")
                        elif c == "q": now.add("quit")
                        elif c == "i": now.add("inventory")
                        elif c in "zxcvb": now.add(f"skill{"zxcvb".index(c)}")
            except Exception:
                pass
        
        # Detect newly pressed (edge detection)
        pressed = now - self._prev
        self._prev = now
        return pressed
    
    def is_held(self, action) -> bool:
        """Check if action key is currently held down."""
        if _user32:
            if action == "up":    return _is_pressed(VK["W"]) or _is_pressed(VK["UP"])
            if action == "down":  return _is_pressed(VK["S"]) or _is_pressed(VK["DOWN"])
            if action == "left":  return _is_pressed(VK["A"]) or _is_pressed(VK["LEFT"])
            if action == "right": return _is_pressed(VK["D"]) or _is_pressed(VK["RIGHT"])
        return False

def wait_for_any_key():
    """Block until any key is pressed."""
    if _user32:
        # Wait for all keys to be released first
        time.sleep(0.1)
        while any(_is_pressed(vk) for vk in VK.values()):
            time.sleep(0.02)
        # Then wait for a press
        while not any(_is_pressed(vk) for vk in VK.values()):
            time.sleep(0.02)
    else:
        try:
            sys.stdin.readline()
        except:
            pass

def read_text_input(max_len=12, prompt="Name: "):
    """Simple text input for nickname. Uses stdin."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        name = sys.stdin.readline().strip()[:max_len]
        return name if name else "Adventurer"
    except:
        return "Adventurer"