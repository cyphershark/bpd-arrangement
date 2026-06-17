# участник и слот
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Participant:
    # Хранит всё про человека: уровень, флаг айрона, предпочтение по открывалке.
    name: str
    level: str = ""        # старичок/новичок
    opening: int = 0       # айроны на открывающих
    ironman: bool = False  # айроны


@dataclass(frozen=True)
class Slot:
    # Координаты места в сетке (рум, позиция 1-я или 2-я, ПРОП/ОПП). frozen - ключ словаря.
    room: int      # 1/2
    position: int  # 1/2
    side: str      # "ПРОП" или "ОПП"

    @property
    def opening(self) -> bool:
        return self.position == 1