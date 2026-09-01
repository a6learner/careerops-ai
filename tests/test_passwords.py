from careerops.security.passwords import PasswordHasher


def test_password_hash_does_not_store_plain_password() -> None:
    hasher = PasswordHasher.recommended()

    password_hash = hasher.hash("correct horse battery staple")

    assert password_hash != "correct horse battery staple"


def test_password_hash_verifies_original_password() -> None:
    hasher = PasswordHasher.recommended()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify("correct horse battery staple", password_hash)


def test_password_hash_rejects_wrong_password() -> None:
    hasher = PasswordHasher.recommended()
    password_hash = hasher.hash("correct horse battery staple")

    assert not hasher.verify("wrong password", password_hash)


def test_hashing_same_password_twice_produces_different_hashes() -> None:
    hasher = PasswordHasher.recommended()

    first_hash = hasher.hash("correct horse battery staple")
    second_hash = hasher.hash("correct horse battery staple")

    assert first_hash != second_hash
    assert hasher.verify("correct horse battery staple", first_hash)
    assert hasher.verify("correct horse battery staple", second_hash)
