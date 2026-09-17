from core.security import verify_gitlab_token


def test_correct_token_is_accepted():
    assert verify_gitlab_token("test-secret") is True


def test_wrong_token_is_rejected():
    assert verify_gitlab_token("nope") is False


def test_missing_token_is_rejected():
    assert verify_gitlab_token(None) is False
    assert verify_gitlab_token("") is False


def test_prefix_of_the_secret_is_rejected():
    assert verify_gitlab_token("test-secre") is False
