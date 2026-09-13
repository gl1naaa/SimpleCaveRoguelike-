import json
import os
import time
from collections import Counter

HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_history.json")
MAX_HISTORY = 50


def _format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


class RunTracker:
    """Tracks stats for a single run and saves history."""

    def __init__(self):
        self.start_time = 0.0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.heal_amount = 0
        self.skill_uses = Counter()
        self.kills = []           # list of enemy name strings
        self.loot_items = []      # list of item name strings
        self.floor = 0
        self.cause_of_death = ""
        self.finished = False

    # ---- logging methods ----

    def start(self):
        self.start_time = time.time()

    def log_damage(self, n):
        self.damage_dealt += max(0, n)

    def log_heal(self, n):
        self.heal_amount += max(0, n)

    def log_skill(self, name):
        self.skill_uses[str(name)] += 1

    def log_kill(self, enemy):
        self.kills.append(str(enemy))

    def log_loot(self, item):
        self.loot_items.append(str(item))

    def finish(self, floor, cause):
        self.floor = floor
        self.cause_of_death = cause
        self.finished = True

    # ---- serialisation ----

    def to_dict(self):
        elapsed = time.time() - self.start_time if self.start_time else 0
        top_skills = self.skill_uses.most_common(3)
        unique_items = sorted(set(self.loot_items))
        return {
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_formatted": _format_time(elapsed),
            "floor": self.floor,
            "cause_of_death": self.cause_of_death,
            "damage_dealt": self.damage_dealt,
            "damage_taken": self.damage_taken,
            "heal_amount": self.heal_amount,
            "kills": len(self.kills),
            "top_skills": top_skills,
            "unique_items": unique_items,
            "total_loot": len(self.loot_items),
        }

    def save_to_history(self):
        """Append this run to run_history.json (max 50 entries)."""
        data = self.to_dict()
        history = []
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []
        history.insert(0, data)
        history = history[:MAX_HISTORY]
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    # ---- static helpers ----

    @staticmethod
    def get_best_record():
        """Return the best run dict (max floor) or None."""
        if not os.path.exists(HISTORY_PATH):
            return None
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
        if not history:
            return None
        return max(history, key=lambda r: r.get("floor", 0))

    @staticmethod
    def load_history():
        """Return the full history list."""
        if not os.path.exists(HISTORY_PATH):
            return []
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
