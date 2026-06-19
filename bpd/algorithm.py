# Алгоритм распределения участников по слотам — все четыре режима.
from __future__ import annotations
import random
from typing import Dict, List, Optional, Set, Tuple

from .models import Participant, Slot


def build_slots() -> List[Slot]:
    # Генерируем все 8 слотов в каноническом порядке (рум 1 - рум 2, поз. 1 - 2, ПРОП - ОПП).
    slots: List[Slot] = []
    for room in (1, 2):
        for position in (1, 2):
            for side in ("ПРОП", "ОПП"):
                slots.append(Slot(room=room, position=position, side=side))
    return slots


def build_units(participants: List[Participant], mode: int) -> List[List[Participant]]:
    # Определяем, КТО с КЕМ играет; слоты распределяются позже в assign_pairs_to_slots.
    newbies = [p for p in participants if p.level == "newbie" and not p.ironman]
    oldmen = [p for p in participants if p.level == "oldman" and not p.ironman]

    random.shuffle(newbies)
    random.shuffle(oldmen)

    units: List[List[Participant]] = []

    if mode == 1:
        # Режим 1: жадно пихаем смешанные пары, пока хватает обоих уровней.
        while newbies and oldmen:
            units.append([newbies.pop(), oldmen.pop()])

        # Остатки одного уровня перемешиваем и ставим в пары случайно — деваться некуда.
        leftovers = newbies + oldmen
        random.shuffle(leftovers)

        while len(leftovers) >= 2:
            units.append([leftovers.pop(), leftovers.pop()])

        if leftovers:
            units.append([leftovers.pop()])

    else:
        # Режим 2: сначала однородные пары новичок+новичок и старичок+старичок.
        while len(newbies) >= 2:
            units.append([newbies.pop(), newbies.pop()])

        while len(oldmen) >= 2:
            units.append([oldmen.pop(), oldmen.pop()])

        # Остатки (если число нечётное в каждой группе) сваливаются в смешанный пул.
        leftovers = newbies + oldmen
        random.shuffle(leftovers)

        while len(leftovers) >= 2:
            units.append([leftovers.pop(), leftovers.pop()])

        if leftovers:
            units.append([leftovers.pop()])

    # Финальный шафл, чтобы порядок обработки пар не выдавал, кто пришёл первым.
    random.shuffle(units)
    return units


def assign_ironmen(
    participants: List[Participant],
    slots: List[Slot],
    room_for_level: Optional[Dict[str, int]],
) -> Dict[Tuple[int, int, str], List[str]]:
    # Первый этап раздачи слотов; айроны идут раньше пар из-за жёстких ограничений.
    assignment: Dict[Tuple[int, int, str], List[str]] = {}
    used_slots: Set[Tuple[int, int, str]] = set()

    ironmen = [p for p in participants if p.ironman]
    random.shuffle(ironmen)

    # opening_ironmen хотят только позицию 1, non_opening — куда угодно.
    opening_ironmen = [p for p in ironmen if p.opening == 1]
    non_opening_ironmen = [p for p in ironmen if p.opening == 0]

    def pick_slot(p: Participant, candidate_pool: List[Slot]) -> Slot:
        available = [
            s for s in candidate_pool
            if (s.room, s.position, s.side) not in used_slots
        ]
        if not available:
            raise ValueError(f"Нет доступных слотов для айрона {p.name}")

        # Если room_for_level задан (режим 2), сначала пробуем предпочитаемый рум.
        if room_for_level is not None:
            preferred_room = room_for_level[p.level]
            preferred = [s for s in available if s.room == preferred_room]
            if preferred:
                return random.choice(preferred)
        return random.choice(available)

    opening_slots = [s for s in slots if s.position == 1]

    # Сначала размещаем айронов с opening=1, иначе они могут не получить открывалку.
    for p in opening_ironmen:
        chosen = pick_slot(p, opening_slots)
        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used_slots.add((chosen.room, chosen.position, chosen.side))

    for p in non_opening_ironmen:
        chosen = pick_slot(p, slots)
        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used_slots.add((chosen.room, chosen.position, chosen.side))

    return assignment


def assign_pairs_to_slots(
    pairs: List[List[Participant]],
    slots: List[Slot],
    current_assignment: Dict[Tuple[int, int, str], List[str]],
    mode: int,
    room_for_level: Optional[Dict[str, int]],
) -> Dict[Tuple[int, int, str], List[str]]:
    # Второй этап: размещение пар на оставшихся после айронов слотах.
    remaining_slots = [
        s for s in slots
        if (s.room, s.position, s.side) not in current_assignment
    ]

    if len(pairs) > len(remaining_slots):
        raise ValueError(
            f"Недостаточно позиций для свободных участников. "
            f"Пары: {len(pairs)}, свободные слоты: {len(remaining_slots)}"
        )

    def place(pair: List[Participant], candidates: List[Slot]) -> None:
        chosen = random.choice(candidates)
        current_assignment[(chosen.room, chosen.position, chosen.side)] = [p.name for p in pair]
        remaining_slots.remove(chosen)

    def place_preferring(pair: List[Participant], target_room: int) -> None:
        in_room = [s for s in remaining_slots if s.room == target_room]
        place(pair, in_room if in_room else remaining_slots)

    # Режим 1 не различает румы по уровню — ставим пары случайно.
    if mode == 1 or room_for_level is None:
        random.shuffle(pairs)
        for pair in pairs:
            place(pair, remaining_slots)
        return current_assignment

    # Классификация пар по уровню.
    def pair_level(pair: List[Participant]) -> str:
        levels = {p.level for p in pair}
        if len(levels) == 1:
            return next(iter(levels))
        return "mixed"

    oldman_pairs = [p for p in pairs if pair_level(p) == "oldman"]
    newbie_pairs = [p for p in pairs if pair_level(p) == "newbie"]
    mixed_pairs = [p for p in pairs if pair_level(p) == "mixed"]
    random.shuffle(oldman_pairs)
    random.shuffle(newbie_pairs)
    random.shuffle(mixed_pairs)

    # Однородные пары идут в свой "родной" рум.
    for pair in oldman_pairs:
        place_preferring(pair, room_for_level["oldman"])
    for pair in newbie_pairs:
        place_preferring(pair, room_for_level["newbie"])

    # Смешанные пары обрабатываем последними, выравнивая загрузку румов.
    for pair in mixed_pairs:
        r1 = sum(1 for s in remaining_slots if s.room == 1)
        r2 = sum(1 for s in remaining_slots if s.room == 2)
        if r1 == 0:
            target = 2
        elif r2 == 0:
            target = 1
        else:
            target = 1 if r1 >= r2 else 2
        place_preferring(pair, target)

    return current_assignment


def assign_mode_3(
    participants: List[Participant],
    slots: List[Slot],
) -> Dict[Tuple[int, int, str], List[str]]:
    # Режим 3 — рум айронов: 4 айрона в одном руме, 4 пары в другом.
    ironmen = [p for p in participants if p.ironman]
    non_ironmen = [p for p in participants if not p.ironman]

    if len(ironmen) != 4:
        raise ValueError(
            f"Режим 3 (рум айронов) требует ровно 4 айрона. Сейчас: {len(ironmen)}."
        )
    if len(non_ironmen) != 8:
        raise ValueError(
            f"Режим 3 (рум айронов) требует ровно 8 не-айронов. Сейчас: {len(non_ironmen)}."
        )

    assignment: Dict[Tuple[int, int, str], List[str]] = {}
    ironman_room = random.choice([1, 2])
    pair_room = 3 - ironman_room

    iron_slots = [s for s in slots if s.room == ironman_room]
    iron_opening = [s for s in iron_slots if s.position == 1]
    iron_closing = [s for s in iron_slots if s.position == 2]
    random.shuffle(iron_opening)
    random.shuffle(iron_closing)

    random.shuffle(ironmen)
    opening_pref = [p for p in ironmen if p.opening == 1]
    no_pref = [p for p in ironmen if p.opening == 0]

    for p in opening_pref:
        pool = iron_opening if iron_opening else iron_closing
        slot = pool.pop()
        assignment[(slot.room, slot.position, slot.side)] = [p.name]

    remaining_iron = iron_opening + iron_closing
    random.shuffle(remaining_iron)
    for p in no_pref:
        slot = remaining_iron.pop()
        assignment[(slot.room, slot.position, slot.side)] = [p.name]

    newbies = [p for p in non_ironmen if p.level == "newbie"]
    oldmen = [p for p in non_ironmen if p.level == "oldman"]
    random.shuffle(newbies)
    random.shuffle(oldmen)

    pairs = []
    while newbies and oldmen:
        pairs.append([newbies.pop(), oldmen.pop()])
    leftovers = newbies + oldmen
    random.shuffle(leftovers)
    while len(leftovers) >= 2:
        pairs.append([leftovers.pop(), leftovers.pop()])

    pair_slots = [s for s in slots if s.room == pair_room]
    random.shuffle(pair_slots)
    for pair in pairs:
        slot = pair_slots.pop()
        assignment[(slot.room, slot.position, slot.side)] = [p.name for p in pair]

    return assignment


def assign_mode_4(
    participants: List[Participant],
    slots: List[Slot],
) -> Dict[Tuple[int, int, str], List[str]]:
    # Режим 4 — один рум: всего 4 команды; айроны сидят соло как обычно.
    ironmen = [p for p in participants if p.ironman]
    non_ironmen = [p for p in participants if not p.ironman]

    n_iron = len(ironmen)
    n_pairs_needed = (len(non_ironmen) + 1) // 2
    if n_iron + n_pairs_needed > 4:
        raise ValueError(
            f"Режим 4 (один рум): слишком много участников. "
            f"{n_iron} айронов и {len(non_ironmen)} остальных не помещаются в 4 стола."
        )

    assignment: Dict[Tuple[int, int, str], List[str]] = {}
    room_used = random.choice([1, 2])
    room_slots = [s for s in slots if s.room == room_used]
    used: Set[Tuple[int, int, str]] = set()

    random.shuffle(ironmen)
    opening_pref = [p for p in ironmen if p.opening == 1]
    no_pref = [p for p in ironmen if p.opening == 0]

    opening_slots = [s for s in room_slots if s.position == 1]
    random.shuffle(opening_slots)

    for p in opening_pref:
        available = [s for s in opening_slots if (s.room, s.position, s.side) not in used]
        if not available:
            available = [s for s in room_slots if (s.room, s.position, s.side) not in used]
        chosen = random.choice(available)
        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used.add((chosen.room, chosen.position, chosen.side))

    for p in no_pref:
        available = [s for s in room_slots if (s.room, s.position, s.side) not in used]
        chosen = random.choice(available)
        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used.add((chosen.room, chosen.position, chosen.side))

    newbies = [p for p in non_ironmen if p.level == "newbie"]
    oldmen = [p for p in non_ironmen if p.level == "oldman"]
    random.shuffle(newbies)
    random.shuffle(oldmen)

    pairs = []
    while newbies and oldmen:
        pairs.append([newbies.pop(), oldmen.pop()])
    leftovers = newbies + oldmen
    random.shuffle(leftovers)
    while len(leftovers) >= 2:
        pairs.append([leftovers.pop(), leftovers.pop()])
    if leftovers:
        pairs.append([leftovers.pop()])

    available_slots = [s for s in room_slots if (s.room, s.position, s.side) not in used]
    random.shuffle(available_slots)
    for pair in pairs:
        chosen = available_slots.pop()
        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name for p in pair]
        used.add((chosen.room, chosen.position, chosen.side))

    return assignment