# Demo CPF checksum

Issue: formatting-only validation accepts 11 digits with invalid check digits.
Reproduction fixture uses synthetic values, fixes checksum validation in the isolated
`customer_registry.services.cpf` helper, and never adds CPF to the registry schema or
persists the input. This demo remains outside the core customer create/update contract.
