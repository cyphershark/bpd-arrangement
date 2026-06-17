# CLI-режим: интерактивный ввод участников из терминала. Запуск: python -m bpd.cli
from __future__ import annotations
import random
import sys
from typing import Dict, List, Optional, Set

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


MAX_PEOPLE = 16  # лимит на 2 рума × 4 позиции × 2 человека
OUTPUT_FILE = "bp_draw.xlsx"
SEED = None  # задайте для повторяющихся раздач при отладке


def prompt_choice(prompt: str, valid: Set[str]) -> str:
    # Крутится в цикле, пока юзер не введёт допустимое значение.
    valid_lower = {v.lower() for v in valid}
    while True:
        value = input(prompt).strip().lower()
        if value in valid_lower:
            return value
        print(f"Пожалуйста, введите одно из: {', '.join(sorted(valid_lower))}")


def prompt_int(prompt: str, valid: Optional[Set[int]] = None) -> int:
    # То же для чисел; valid none — любое целое подойдёт.
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
    # Парсит '1,3,5-7' в множество индексов для выбора айронов сразу пачкой.
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
    print("Нажмите Enter для пустой строки или напишите 'done' для завершения регистрации.\n")

    participants: List[Participant] = []
    while True:
        name = input(f"Участники #{len(participants) + 1}: ").strip()
        if not name or name.lower() == "done":
            break
        participants.append(Participant(name=name))
        if len(participants) >= MAX_PEOPLE:
            print(f"\nДостигнут максимум {MAX_PEOPLE} участников.")
            break
    return participants


def choose_ironmen(participants: List[Participant]) -> None:
    print("\nВыбор айронов")
    print("Введите номера участников через запятую/дефис.")
    print("Пример: 1,4,7-9")
    print("Нажмите Enter если айронов нет.\n")

    while True:
        raw = input("Айроны: ").strip()
        try:
            selected = parse_index_selection(raw, len(participants))
            break
        except ValueError:
            print("Используйте только цифры, запятые и диапазоны вида 2-5.")

    for idx in selected:
        participants[idx - 1].ironman = True


def choose_mode() -> int:
    print("\nСтиль расстановки")
    print("1 = Смешанные пары старичков и новичков")
    print("2 = Раздельные румы по уровню")
    print("3 = Рум айронов (ровно 4 айрона + 4 пары)")
    print("4 = Один рум (4 команды)")
    return prompt_int("Изберите стиль (1/2/3/4): ", valid={1, 2, 3, 4})


def collect_levels_and_opening(participants: List[Participant]) -> None:
    print("\nУровни участников")
    print("Для каждого участника введите его уровень.")
    print("Открывающая позиция запрашивается только у айронов.\n")

    for i, p in enumerate(participants, start=1):
        print(f"{i}. {p.name}")
        level = prompt_choice("   Уровень [n=новичок, o=старичок]: ", {"n", "o"})
        p.level = "newbie" if level == "n" else "oldman"

        if p.ironman:
            p.opening = prompt_int("   Открывающая позиция [0=нет, 1=да]: ", valid={0, 1})
        else:
            p.opening = 0


def print_summary(participants: List[Participant], mode: int) -> None:
    print("\nФинальная проверка")
    print(f"Режим: {mode}")
    print("-" * 82)
    print(f"{'#':<4} {'Имя':<22} {'Уровень':<10} {'Айрон':<10} {'Открывалка':<10}")
    print("-" * 82)
    for i, p in enumerate(participants, start=1):
        print(
            f"{i:<4} {p.name:<22} {p.level:<10} "
            f"{('да' if p.ironman else 'нет'):<10} "
            f"{(p.opening if p.ironman else '-'):<10}"
        )
    print("-" * 82)


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
            f"Макс. количество с айронами: {capacity}\n"
        )
        return

    mode = choose_mode()
    collect_levels_and_opening(participants)

    print_summary(participants, mode)
    confirm = prompt_choice("Создаём таблицу? [y/n]: ", {"y", "n"})
    if confirm != "y":
        print("Отменено.")
        return

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

    write_excel(participants, assignment, OUTPUT_FILE)
    print(f"\nСделано. Сохранено: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОтменено администратором.")
        sys.exit(1)