from app.types import Settings


def test_settings():
    s = Settings("/set mode auto helper_chat_id 123 chat_url abcd")
    t = Settings({"mode": "auto", "helper_chat_id": "123", "chat_url": "abcd"})
    assert s == t


def test_settings_with_verification_msg():
    s = Settings(
        "/set mode auto helper_chat_id 123 chat_url abcd verification_msg\n12345678909"
    )
    print(s)
    assert len(s) == 4


def test_settings_pretty_print():
    s = Settings("/set mode auto helper_chat_id 123")
    assert len(s) == 2
