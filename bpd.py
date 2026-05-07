from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


MAX_PEOPLE = 16
OUTPUT_FILE = "bp_draw.xlsx"
SEED = None  # можно задать высоту для повторяющихся блоков 


@dataclass
class Participant:
    name: str
    level: str = ""        # старичок/новичок
    opening: int = 0       # айроны на открывающих
    ironman: bool = False  # айроны


@dataclass(frozen=True)
class Slot:
    room: int      # 1/2
    position: int  # 1/2
    side: str      # "ПРОП" или "ОПП"

    @property
    def opening(self) -> bool:
        return self.position == 1


def prompt_choice(prompt: str, valid: Set[str]) -> str:
    valid_lower = {v.lower() for v in valid}
    while True:
        value = input(prompt).strip().lower()
        if value in valid_lower:
            return value
        print(f"Пожалуйста, введите одно из: {', '.join(sorted(valid_lower))}")


def prompt_int(prompt: str, valid: Optional[Set[int]] = None) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if valid is not None and value not in valid:
            print(f"Please enter one of: {sorted(valid)}")
            continue
        return value


def parse_index_selection(raw: str, max_index: int) -> Set[int]:
    """
    Accepts input like:
      1,3,5-7
    Returns 1-based indices.
    """
    selected: Set[int] = set()
    raw = raw.strip()
    if not raw:
        return selected

    tokens = raw.replace(" ", "").split(",")
    for token in tokens:
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start = int(left)
            end = int(right)
            if start > end:
                start, end = end, start
            for n in range(start, end + 1):
                if 1 <= n <= max_index:
                    selected.add(n)
        else:
            n = int(token)
            if 1 <= n <= max_index:
                selected.add(n)
    return selected


def collect_participants() -> List[Participant]:
    print("\nРегистрация участников")
    print("Последовательно введите имена участников.")
    print("Жмякните Enter для пустой строки, или напишите 'done' для завершения реєстрації.\n")

    participants: List[Participant] = []
    while True:
        name = input(f"Участники #{len(participants) + 1}: ").strip()
        if not name or name.lower() == "done":
            break
        participants.append(Participant(name=name))
        if len(participants) >= MAX_PEOPLE:
            print(f"\nReached the maximum of {MAX_PEOPLE} participants.")
            break
    return participants


def choose_ironmen(participants: List[Participant]) -> None:
    print("\nIronman selection")
    print("Enter participant numbers to mark as ironmen.")
    print("Example: 1,4,7-9")
    print("Press Enter for none.\n")

    while True:
        raw = input("Айроны: ").strip()
        try:
            selected = parse_index_selection(raw, len(participants))
            break
        except ValueError:
            print("Please use only numbers, commas, and ranges like 2-5.")

    for idx in selected:
        participants[idx - 1].ironman = True


def choose_mode() -> int:
    print("\nСтиль расстановки")
    print("1 = Пары старички + новички")
    print("2 = Новички и старички в разных румах")
    return prompt_int("Изберите стиль (1/2): ", valid={1, 2})


def collect_levels_and_opening(participants: List[Participant]) -> None:
    print("\nИмена участников")
    print("Для каждого участника введите его уровень.")
    print("Открывающая позиция доступна только айронам.\n")

    for i, p in enumerate(participants, start=1):
        print(f"{i}. {p.name}")
        level = prompt_choice("   Уровень [n=новичок, o=старличок]: ", {"n", "o"})
        p.level = "newbie" if level == "n" else "oldman"

        if p.ironman:
            p.opening = prompt_int("   Открывающая позиция [0=нет, 1=да]: ", valid={0, 1})
        else:
            p.opening = 0


def print_summary(participants: List[Participant], mode: int) -> None:
    print("\nФинальная перевірка")
    print(f"Mode: {mode}")
    print("-" * 82)
    print(f"{'#':<4} {'Name':<22} {'Level':<10} {'Ironman':<10} {'Opening':<10}")
    print("-" * 82)
    for i, p in enumerate(participants, start=1):
        print(
            f"{i:<4} {p.name:<22} {p.level:<10} "
            f"{('yes' if p.ironman else 'no'):<10} "
            f"{(p.opening if p.ironman else '-'):<10}"
        )
    print("-" * 82)


def build_slots() -> List[Slot]:
    slots: List[Slot] = []
    for room in (1, 2):
        for position in (1, 2):
            for side in ("ПРОП", "ОПП"):
                slots.append(Slot(room=room, position=position, side=side))
    return slots


def pair_leftovers_randomly(pool: List[Participant]) -> List[List[Participant]]:
    random.shuffle(pool)
    units: List[List[Participant]] = []
    while len(pool) >= 2:
        units.append([pool.pop(), pool.pop()])
    if pool:
        units.append([pool.pop()])
    return units


def build_units(participants: List[Participant], mode: int) -> List[List[Participant]]:
    newbies = [p for p in participants if p.level == "newbie" and not p.ironman]
    oldmen = [p for p in participants if p.level == "oldman" and not p.ironman]

    random.shuffle(newbies)
    random.shuffle(oldmen)

    units: List[List[Participant]] = []

    if mode == 1:
        # Prefer mixed pairs: newbie + oldman
        while newbies and oldmen:
            units.append([newbies.pop(), oldmen.pop()])

        leftovers = newbies + oldmen
        random.shuffle(leftovers)

        while len(leftovers) >= 2:
            units.append([leftovers.pop(), leftovers.pop()])

        if leftovers:
            units.append([leftovers.pop()])

    else:
        # Mode 2: separate by level first
        while len(newbies) >= 2:
            units.append([newbies.pop(), newbies.pop()])

        while len(oldmen) >= 2:
            units.append([oldmen.pop(), oldmen.pop()])

        leftovers = newbies + oldmen
        random.shuffle(leftovers)

        while len(leftovers) >= 2:
            units.append([leftovers.pop(), leftovers.pop()])

        if leftovers:
            units.append([leftovers.pop()])

    random.shuffle(units)
    return units


def assign_ironmen(
    participants: List[Participant],
    slots: List[Slot],
) -> Dict[Tuple[int, int, str], List[str]]:
    """
    Ironmen placement rules:
    - One ironman occupies an entire side alone
    - Never two ironmen in the same side
    - Opening-pref ironmen only in position 1
    - Non-opening ironmen distributed randomly across all remaining slots
    """

    assignment: Dict[Tuple[int, int, str], List[str]] = {}

    opening_slots = [s for s in slots if s.position == 1]
    normal_slots = slots[:]

    random.shuffle(opening_slots)
    random.shuffle(normal_slots)

    ironmen = [p for p in participants if p.ironman]
    random.shuffle(ironmen)

    used_slots: Set[Tuple[int, int, str]] = set()

    # 1. Opening-preference ironmen first
    opening_ironmen = [p for p in ironmen if p.opening == 1]
    non_opening_ironmen = [p for p in ironmen if p.opening == 0]

    for p in opening_ironmen:
        available = [
            s for s in opening_slots
            if (s.room, s.position, s.side) not in used_slots
        ]

        if not available:
            raise ValueError(
                f"Нет открывающих слотов для айрона {p.name}"
            )

        chosen = random.choice(available)

        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used_slots.add((chosen.room, chosen.position, chosen.side))

    # 2. Remaining ironmen completely random
    for p in non_opening_ironmen:
        available = [
            s for s in normal_slots
            if (s.room, s.position, s.side) not in used_slots
        ]

        if not available:
            raise ValueError(
                f"Не осталось слотов для айрона {p.name}"
            )

        chosen = random.choice(available)

        assignment[(chosen.room, chosen.position, chosen.side)] = [p.name]
        used_slots.add((chosen.room, chosen.position, chosen.side))

    return assignment


def assign_pairs_to_slots(
    pairs: List[List[Participant]],
    slots: List[Slot],
    current_assignment: Dict[Tuple[int, int, str], List[str]],
    mode: int,
) -> Dict[Tuple[int, int, str], List[str]]:
    remaining_slots = [
        s for s in slots
        if (s.room, s.position, s.side) not in current_assignment
    ]

    if len(pairs) > len(remaining_slots):
        raise ValueError(
            f"Недостаточно позиций для свободных участников."
            f"Пары: {len(pairs)}, свободные слоты: {len(remaining_slots)}"
        )

    random.shuffle(pairs)

    for pair in pairs:
        chosen = random.choice(remaining_slots)
        current_assignment[(chosen.room, chosen.position, chosen.side)] = [p.name for p in pair]
        remaining_slots.remove(chosen)

    return current_assignment


def write_excel(
    participants: List[Participant],
    assignment: Dict[Tuple[int, int, str], List[str]],
    output_path: str,
) -> None:
    wb = Workbook()

    # Participants sheet
    ws_p = wb.active
    ws_p.title = "Участники"
    ws_p.append(["#", "Имя", "Уровень", "Айрон", "Открывающий"])
    for i, p in enumerate(participants, start=1):
        ws_p.append([i, p.name, p.level, "да" if p.ironman else "нет", p.opening if p.ironman else ""])

    # Draw sheet
    ws = wb.create_sheet("Draw")

    bold = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    gov_fill = PatternFill("solid", fgColor="5B88B4")
    opp_fill = PatternFill("solid", fgColor="F5E08A")
    body_fill_gov = PatternFill("solid", fgColor="D9E6F2")
    body_fill_opp = PatternFill("solid", fgColor="FBF2CC")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Fixed widths to avoid stretching
    widths = {1: 10, 2: 10, 3: 18, 4: 18, 5: 18, 6: 18}
    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    row = 2
    for room in (1, 2):
        # Header
        ws[f"A{row}"] = "Рум"
        ws[f"B{row}"] = "Позиция"
        ws[f"C{row}"] = "ПРОП"
        ws[f"E{row}"] = "ОПП"

        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=6)

        for ref in (f"A{row}", f"B{row}", f"C{row}", f"E{row}"):
            ws[ref].font = bold
            ws[ref].alignment = center
            ws[ref].border = border

        ws[f"C{row}"].fill = gov_fill
        ws[f"E{row}"].fill = opp_fill

        data_row_1 = row + 1
        data_row_2 = row + 2

        ws.merge_cells(start_row=data_row_1, start_column=1, end_row=data_row_2, end_column=1)
        ws[f"A{data_row_1}"] = room
        ws[f"A{data_row_1}"].alignment = center
        ws[f"A{data_row_1}"].border = border
        ws[f"A{data_row_1}"].font = bold

        for position, r in ((1, data_row_1), (2, data_row_2)):
            ws[f"B{r}"] = position
            ws[f"B{r}"].alignment = center
            ws[f"B{r}"].border = border

            for col in (3, 4):
                ws.cell(r, col).fill = body_fill_gov
            for col in (5, 6):
                ws.cell(r, col).fill = body_fill_opp

            for col in range(1, 7):
                ws.cell(r, col).alignment = center
                ws.cell(r, col).border = border

            side_names = {
                "ПРОП": assignment.get((room, position, "ПРОП"), []),
                "ОПП": assignment.get((room, position, "ОПП"), []),
            }

            gov = side_names["ПРОП"] + ["", ""]
            ws[f"C{r}"] = gov[0]
            ws[f"D{r}"] = gov[1]

            opp = side_names["ОПП"] + ["", ""]
            ws[f"E{r}"] = opp[0]
            ws[f"F{r}"] = opp[1]

            ws.row_dimensions[r].height = 30

        row += 4  # форматирование

    # Форматирование участников
    for cell in ws_p[1]:
        cell.font = bold
        cell.alignment = center
        cell.border = border

    for row_cells in ws_p.iter_rows():
        for cell in row_cells:
            cell.alignment = center
            cell.border = border

    for col_idx, width in {1: 6, 2: 22, 3: 12, 4: 10, 5: 10}.items():
        ws_p.column_dimensions[get_column_letter(col_idx)].width = width

    wb.save(output_path)


def main() -> None:
    if SEED is not None:
        random.seed(SEED)

    print("Генератор сетки для БПД")
    participants = collect_participants()

    if not participants:
        print("Участники не введены. Выход.")
        return

    choose_ironmen(participants)

    ironman_count = sum(1 for p in participants if p.ironman)
    capacity = MAX_PEOPLE - ironman_count
    if len(participants) > capacity:
        print(
            f"\nСлишком много участников.\n"
            f"Участников введено: {len(participants)}\n"
            f"Айронов: {ironman_count}\n"
            f"Макс количество с айронами: {capacity}\n"
        )
        return

    mode = choose_mode()
    collect_levels_and_opening(participants)

    print_summary(participants, mode)
    confirm = prompt_choice("Создаём таблицу из имеющихся данных? [y/n]: ", {"y", "n"})
    if confirm != "y":
        print("Отменено.")
        return

    slots = build_slots()
    assignment = assign_ironmen(participants, slots)
    remaining_people = [p for p in participants if not p.ironman]
    units = build_units(remaining_people, mode)
    assignment = assign_pairs_to_slots(units, slots, assignment, mode)

    write_excel(participants, assignment, OUTPUT_FILE)
    print(f"\nСделано. Сохранено: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОтменено администратором.")
        sys.exit(1)