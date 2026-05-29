from gateway.auth.passwords import hash_password, verify_password


def test_hash_is_not_plaintext():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$2")


def test_verify_correct_password():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_two_hashes_of_same_password_differ():
    assert hash_password("secret123") != hash_password("secret123")
