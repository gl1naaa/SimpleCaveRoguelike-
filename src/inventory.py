from typing import List, Optional, Tuple
from items import Item
from config import INVENTORY_SIZE

# Color map for rarities
RARITY_COLORS = {
    "common": "255,255,255",
    "uncommon": "0,200,0",
    "rare": "0,120,255",
    "epic": "180,0,255",
    "mythic": "255,50,50",
    "legendary": "255,215,0",
    "unique": "255,180,0",
}

def _rst():
    return "\x1b[0m"

def _fg(r,g,b):
    return f"\x1b[38;2;{r};{g};{b}m"

def _bold():
    return "\x1b[1m"

def rarity_color(rarity):
    rgb = RARITY_COLORS.get(rarity, "255,255,255")
    r, g, b = map(int, rgb.split(","))
    return _fg(r, g, b)


class Inventory:
    def __init__(self, max_slots: int = 20):
        self.slots: List[Optional[Item]] = [None] * max_slots
        self.max_slots = max_slots
        self.equipment = {
            "weapon": None,
            "armor": None,
            "accessory": None,
        }
        self.gold = 0
        self.selected_slot = 0

    def add_item(self, item: Item) -> bool:
        """Add item to inventory. Returns True if successful."""
        # Stack consumables
        if item.item_type == "consumable" and item.stackable:
            for i, slot in enumerate(self.slots):
                if slot and slot.item_type == "consumable" and slot.name == item.name:
                    slot.quantity += item.quantity
                    return True
        # Find empty slot
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = item
                return True
        return False  # inventory full

    def remove_item(self, index: int) -> Optional[Item]:
        """Remove and return item at index."""
        if 0 <= index < self.max_slots and self.slots[index] is not None:
            item = self.slots[index]
            self.slots[index] = None
            return item
        return None

    def get_item(self, index: int) -> Optional[Item]:
        if 0 <= index < self.max_slots:
            return self.slots[index]
        return None

    def use_item(self, index: int) -> Tuple[bool, str]:
        """Use an item. Returns (success, message)."""
        item = self.get_item(index)
        if not item:
            return False, "Empty slot!"
        if item.item_type == "consumable":
            name = item.name
            if item.quantity > 1:
                item.quantity -= 1
            else:
                self.remove_item(index)
            return True, f"Used {name}"
        elif item.item_type == "weapon":
            self.equip(index, "weapon")
            return True, f"Equipped {item.name}"
        elif item.item_type == "armor":
            self.equip(index, "armor")
            return True, f"Equipped {item.name}"
        elif item.item_type == "accessory":
            self.equip(index, "accessory")
            return True, f"Equipped {item.name}"
        elif item.item_type == "skill_book":
            self.remove_item(index)
            return True, f"Learned skill from {item.name}"
        return False, "Can't use this!"

    def equip(self, inv_index: int, slot: str) -> Optional[Item]:
        """Equip item from inventory, return previously equipped item."""
        item = self.get_item(inv_index)
        if not item:
            return None
        old = self.equipment.get(slot)
        self.equipment[slot] = item
        self.remove_item(inv_index)
        if old:
            self.add_item(old)
        return old

    def get_equipped(self, slot: str) -> Optional[Item]:
        return self.equipment.get(slot)

    def get_stats(self) -> dict:
        """Get total stats from equipment."""
        stats = {"atk": 0, "def": 0, "hp": 0, "mp": 0, "speed": 0, "crit": 0, "str": 0, "agi": 0, "int": 0}
        for slot, item in self.equipment.items():
            if item:
                for k, v in item.stats.items():
                    if k in stats:
                        stats[k] += v
        return stats

    def render(self) -> List[str]:
        """Render inventory UI."""
        lines = []
        lines.append("")
        lines.append(f"  {_bold()}{_fg(255,215,0)}INVENTORY{_rst()}")
        lines.append(f"  Gold: {_fg(255,215,0)}{self.gold}{_rst()}")
        lines.append("")

        # Equipment
        lines.append(f"  {_bold()}{_fg(0,200,200)}EQUIPMENT{_rst()}")
        for slot_name in ["weapon", "armor", "accessory"]:
            item = self.equipment.get(slot_name)
            label = slot_name.upper()
            if item:
                lines.append(f"  {label:12s} {rarity_color(item.rarity)}{item.name}{_rst()}")
            else:
                lines.append(f"  {label:12s} (empty)")
        lines.append("")

        # Inventory grid
        lines.append(f"  {_bold()}{_fg(0,200,200)}ITEMS{_rst()}")
        for i in range(self.max_slots):
            item = self.slots[i]
            marker = ">>>" if i == self.selected_slot else "   "
            if item:
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"  {marker} {i:2d}. {rarity_color(item.rarity)}{item.name}{_rst()}{qty}")
            else:
                lines.append(f"  {marker} {i:2d}. ---")
        lines.append("")
        return lines

    def render_compact(self) -> List[str]:
        """Render compact bottom-bar inventory."""
        lines = []
        for i in range(min(10, self.max_slots)):
            item = self.slots[i]
            marker = _bold() + _fg(255,255,0) + ">>>" + _rst() if i == self.selected_slot else "   "
            if item:
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"{marker}{i:2d}.{rarity_color(item.rarity)}{item.name[:10]}{_rst()}{qty}")
            else:
                lines.append(f"{marker}{i:2d}. ---")
        return lines
