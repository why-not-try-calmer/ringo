from dataclasses import asdict
from toml import loads
from app.types import Log, Settings


def test_settings():
    s = Settings("/set mode auto helper_chat_id 123 chat_url abcd")
    t = Settings({"mode": "auto", "helper_chat_id": "123", "chat_url": "abcd"})
    print(s.as_dict_no_none())
    assert s == t


def test_settings_with_verification_msg():
    s = Settings(
        "/set mode auto helper_chat_id 123 chat_url abcd verification_msg\nEspace de discussion fribourgeois basé à la Gare CFF. Convivialité et bonne humeur bienvenues! Crypto, drogues, complots et sexe bannis."
    )
    print(s.as_dict_no_none())
    assert len(s) == 4


def test_settings_pretty_print():
    s = Settings("/set chat_url 123")
    print(s.as_dict_no_none())
    assert len(s) == 1


def test_string():
    with open("strings.toml", "r") as f:
        r = f.read()
        strings = loads(r)
        assert len(strings) >= 4


def test_log():
    l = Log("1234", 1, 1, "my_name")
    d = asdict(l)
    assert len(d) == 5
