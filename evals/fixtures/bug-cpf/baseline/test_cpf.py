from cpf import is_valid_cpf


def test_valid_synthetic_value_is_accepted():
    assert is_valid_cpf("52998224725")


def test_invalid_synthetic_check_digit_is_rejected():
    assert not is_valid_cpf("52998224726")
