"""Checksum validation for synthetic CPF issue reproduction; values are never stored."""

from __future__ import annotations

import re


def is_valid_cpf(value: str) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{11}", value) is None:
        return False
    digits = value
    if len(set(digits)) == 1:
        return False
    numbers = [int(character) for character in digits]
    first_sum = sum(
        number * weight
        for number, weight in zip(numbers[:9], range(10, 1, -1), strict=True)
    )
    first = (first_sum * 10) % 11
    first = 0 if first == 10 else first
    second_sum = sum(
        number * weight
        for number, weight in zip(numbers[:10], range(11, 1, -1), strict=True)
    )
    second = (second_sum * 10) % 11
    second = 0 if second == 10 else second
    return numbers[9:] == [first, second]
