from app.search.normalizer import mask_id, normalize_id, normalize_name, numeric_token_pattern


def test_identification_normalization_removes_all_formatting():
    assert normalize_id(" 1.234, 567-890 ") == "1234567890"


def test_names_with_accents_and_compound_surnames():
    assert normalize_name("  María-José   De la Cruz Núñez ") == "MARIA JOSE DE LA CRUZ NUNEZ"


def test_numeric_boundary_prevents_partial_matches():
    pattern = numeric_token_pattern("123456")
    assert pattern.search("CC 123456 confirmado")
    assert not pattern.search("CC 91234567 confirmado")


def test_masking_identification_number():
    assert mask_id("1234567890") == "1.234.***.890"
    masked = mask_id("900000001")
    assert "000" not in masked
    assert masked.endswith("001")
