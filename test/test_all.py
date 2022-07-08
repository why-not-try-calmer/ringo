from app.types import Settings


def test_settings():
    s = Settings("/set mode auto helper_chat_id 123 chat_url abcd")
    t = Settings({"mode": "auto", "helper_chat_id": "123", "chat_url": "abcd"})
    assert s == t


def test_settings_pretty_print():
    settings = Settings("/set mode auto helper_chat_id 123")
    s = str(settings)
    assert len(s) > 10
