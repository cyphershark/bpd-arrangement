# Веб-вход: run_draw принимает данные из JSON, возвращает байты xlsx и assignment.
from __future__ import annotations
import io
import random
from typing import Dict, List, Optional

from .models import Participant
from .algorithm import (
    assign_ironmen,
    assign_mode_3,
    assign_mode_4,
    assign_pairs_to_slots,
    build_slots,
    build_units,
)
from .excel import write_excel


def run_draw(participants_data: List[Dict], mode: int) -> Dict:
    """Точка входа для веб-интерфейса.
    аргументы:
        participants_data: список словарей с полями name, level, ironman, opening
        режим: 1, 2, 3 или 4
    возврат:
        dict с 'xlsx' (список байтов) и 'assignment' (словарь "room_pos_side" -> имена)
    """
    # Повышение энтропии при каждом вызове, иначе пиодиди может выдавать одинаковые пары.
    random.seed()

    participants = [
        Participant(
            name=p["name"],
            level=p["level"],
            ironman=bool(p["ironman"]),
            opening=int(p["opening"]),
        )
        for p in participants_data
    ]

    slots = build_slots()

    if mode == 1:
        assignment = assign_ironmen(participants, slots, None)
        remaining = [p for p in participants if not p.ironman]
        units = build_units(remaining, mode)
        assignment = assign_pairs_to_slots(units, slots, assignment, mode, None)
    elif mode == 2:
        oldman_room = random.choice([1, 2])
        room_for_level: Optional[Dict[str, int]] = {
            "oldman": oldman_room,
            "newbie": 3 - oldman_room,
        }
        assignment = assign_ironmen(participants, slots, room_for_level)
        remaining = [p for p in participants if not p.ironman]
        units = build_units(remaining, mode)
        assignment = assign_pairs_to_slots(units, slots, assignment, mode, room_for_level)
    elif mode == 3:
        assignment = assign_mode_3(participants, slots)
    elif mode == 4:
        assignment = assign_mode_4(participants, slots)
    else:
        raise ValueError(f"Неизвестный режим: {mode}")

    buf = io.BytesIO()
    write_excel(participants, assignment, buf)

    serializable = {
        f"{room}_{pos}_{side}": names
        for (room, pos, side), names in assignment.items()
    }

    return {"xlsx": list(buf.getvalue()), "assignment": serializable}