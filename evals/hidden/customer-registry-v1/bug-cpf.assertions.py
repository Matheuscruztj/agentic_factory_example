"""Hidden deterministic assertions; copy only into the isolated evaluator sandbox."""
from customer_registry.services.cpf import is_valid_cpf

assert is_valid_cpf("52998224725") is True
assert is_valid_cpf("52998224726") is False
assert is_valid_cpf("11111111111") is False
assert is_valid_cpf("529.982.247-25") is True
