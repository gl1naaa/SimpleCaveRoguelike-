from typing import List, Optional, Tuple
from items import Item
from config import INVENTORY_SIZE
from ui import fg, rst, bold, rarity_color, vis_len, BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_LT, BOX_RT, rainbow


class Inventory:
    # All equipment slots in order
    EQUIP_SLOTS = ["weapon", "helmet", "chest", "legs", "boots", "gloves", "necklace", "ring1", "ring2", "cape"]
    # Map item_type to target slot(s)
    TYPE_TO_SLOT = {
        "weapon": "weapon",
        "helmet": "helmet",
        "chest": "chest",
        "legs": "legs",
        "boots": "boots",
        "gloves": "gloves",
        "necklace": "necklace",
        "ring": None,  # special: find first empty ring slot
        "cape": "cape",
    }

    def __init__(self, max_slots: int = 20):
        self.slots: List[Optional[Item]] = [None] * max_slots
        self.max_slots = max_slots
        self.equipment = {slot: None for slot in self.EQUIP_SLOTS}
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
        elif item.item_type in ("weapon", "helmet", "chest", "legs", "boots",
                                "gloves", "necklace", "cape"):
            slot = self.TYPE_TO_SLOT[item.item_type]
            self.equip(index, slot)
            return True, f"Equipped {item.name}"
        elif item.item_type == "ring":
            # Find first empty ring slot, or use ring1
            if not self.equipment.get("ring1"):
                self.equip(index, "ring1")
            elif not self.equipment.get("ring2"):
                self.equip(index, "ring2")
            else:
                self.equip(index, "ring1")
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
        lines.append(f"  {bold()}{fg(255,215,0)}INVENTORY{rst()}")
        lines.append(f"  Gold: {fg(255,215,0)}{self.gold}{rst()}")
        lines.append("")

        # Equipment
        lines.append(f"  {bold()}{fg(0,200,200)}EQUIPMENT{rst()}")
        for slot_name in self.EQUIP_SLOTS:
            item = self.equipment.get(slot_name)
            label = slot_name.upper()[:9]
            if item:
                lines.append(f"  {label:10s} {rarity_color(item.rarity)}{item.name}{rst()}")
            else:
                lines.append(f"  {label:10s} (empty)")
        lines.append("")

        # Inventory grid
        lines.append(f"  {bold()}{fg(0,200,200)}ITEMS{rst()}")
        for i in range(self.max_slots):
            item = self.slots[i]
            marker = ">>>" if i == self.selected_slot else "   "
            if item:
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"  {marker} {i:2d}. {rarity_color(item.rarity)}{item.name}{rst()}{qty}")
            else:
                lines.append(f"  {marker} {i:2d}. ---")
        lines.append("")
        return lines

    def render_compact(self) -> List[str]:
        """Render compact bottom-bar inventory."""
        lines = []
        for i in range(min(10, self.max_slots)):
            item = self.slots[i]
            marker = bold() + fg(255,255,0) + ">>>" + rst() if i == self.selected_slot else "   "
            if item:
                qty = f" x{item.quantity}" if item.quantity > 1 else ""
                lines.append(f"{marker}{i:2d}.{rarity_color(item.rarity)}{item.name[:10]}{rst()}{qty}")
            else:
                lines.append(f"{marker}{i:2d}. ---")
        return lines


# ============================================================
#  Inventory Input Handler (shared by city & dungeon)
# ============================================================
GRID_COLS = 6
MAX_EQ = 10  # equipment slot count

def handle_inventory_input(player, keys, game_time, inv_cursor, inv_col, inv_nav_cd, log, render_fn):
    """Process inventory navigation, equip/use/unequip, and drop.
    Calls render_fn(player, inv_cursor, inv_col) when the display changes.
    Returns (inv_cursor, inv_col, inv_nav_cd).
    """
    GRID_SLOTS = player.inventory.max_slots
    inv_moved = False
    if game_time - inv_nav_cd >= 0.08:
        if "up" in keys:
            if inv_col == 0: inv_cursor = (inv_cursor - GRID_COLS) % GRID_SLOTS
            elif inv_col == 1: inv_cursor = (inv_cursor - 1) % MAX_EQ
            render_fn(player, inv_cursor, inv_col)
            inv_moved = True
        elif "down" in keys:
            if inv_col == 0: inv_cursor = (inv_cursor + GRID_COLS) % GRID_SLOTS
            elif inv_col == 1: inv_cursor = (inv_cursor + 1) % MAX_EQ
            render_fn(player, inv_cursor, inv_col)
            inv_moved = True
        elif "left" in keys:
            if inv_col == 0:
                if inv_cursor % GRID_COLS == 0:
                    inv_col = 1; inv_cursor = min(inv_cursor // GRID_COLS, MAX_EQ - 1)
                else: inv_cursor -= 1
            elif inv_col == 1:
                inv_col = 0; inv_cursor = min(inv_cursor, GRID_SLOTS - 1)
            render_fn(player, inv_cursor, inv_col)
            inv_moved = True
        elif "right" in keys:
            if inv_col == 0:
                if inv_cursor % GRID_COLS == GRID_COLS - 1:
                    inv_col = 1; inv_cursor = min(inv_cursor // GRID_COLS, MAX_EQ - 1)
                else: inv_cursor += 1
            elif inv_col == 1:
                inv_col = 0; inv_cursor = min(inv_cursor, GRID_SLOTS - 1)
            render_fn(player, inv_cursor, inv_col)
            inv_moved = True
        if inv_moved: inv_nav_cd = game_time
    if "action" in keys:
        if inv_col == 0 and 0 <= inv_cursor < player.inventory.max_slots:
            item = player.inventory.get_item(inv_cursor)
            if item:
                itype = item.item_type
                if itype in ("weapon", "helmet", "chest", "legs", "boots", "gloves", "necklace", "cape"):
                    slot = Inventory.TYPE_TO_SLOT.get(itype, itype)
                    player.inventory.equip(inv_cursor, slot)
                    player._recalc_stats()
                    log.append(f"Equipped {item.name} [{item.rarity}]")
                elif itype == "ring":
                    if not player.inventory.equipment.get("ring1"):
                        player.inventory.equip(inv_cursor, "ring1")
                    elif not player.inventory.equipment.get("ring2"):
                        player.inventory.equip(inv_cursor, "ring2")
                    else:
                        player.inventory.equip(inv_cursor, "ring1")
                    player._recalc_stats()
                    log.append(f"Equipped {item.name} [{item.rarity}]")
                elif itype == "consumable":
                    ok, msg = player.inventory.use_item(inv_cursor)
                    log.append(msg)
                    if item.consumable_effect == "heal": player.heal(item.consumable_value)
                    elif item.consumable_effect == "mana": player.restore_mp(item.consumable_value)
        elif inv_col == 1:
            eq_slots = player.inventory.EQUIP_SLOTS
            if 0 <= inv_cursor < len(eq_slots):
                slot = eq_slots[inv_cursor]
                old_item = player.inventory.equipment.get(slot)
                if old_item:
                    player.inventory.equipment[slot] = None
                    player.inventory.add_item(old_item)
                    player._recalc_stats()
                    log.append(f"Unequipped {old_item.name}")
        render_fn(player, inv_cursor, inv_col)
    if "delete" in keys:
        if inv_col == 0 and 0 <= inv_cursor < player.inventory.max_slots:
            item = player.inventory.get_item(inv_cursor)
            if item:
                player.inventory.remove_item(inv_cursor)
                log.append(f"Dropped {item.name}")
                render_fn(player, inv_cursor, inv_col)
    return inv_cursor, inv_col, inv_nav_cd
