"""Deliberately defective source used only to reproduce the synthetic CPF issue."""


def is_valid_cpf(value: str) -> bool:
    return value.isdigit() and len(value) == 11
