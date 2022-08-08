from toml import loads
from app.types import (
    Questionnaire,
    Dialog,
    DialogManager,
    UserLog,
    Settings,
)


def test_settings():
    s = Settings("/set mode auto helper_chat_id 123 chat_url abcd")
    t = Settings({"mode": "auto", "helper_chat_id": "123", "chat_url": "abcd"})
    assert s.as_dict() == t.as_dict() and len(t.unassigned) == 7


def test_settings_with_verification_msg():
    s = Settings(
        "/set mode auto helper_chat_id 123 chat_url abcd verification_msg\nEspace de discussion fribourgeois basé à la Gare CFF. Convivialité et bonne humeur bienvenues! Crypto, drogues, complots et sexe bannis."
    )
    assert len(s) == 4


def test_settings_pretty_print():
    s = Settings("/set chat_url 123")
    print(s.as_dict())
    assert len(s) == 1


def test_string():
    with open("strings.toml", "r") as f:
        r = f.read()
        strings = loads(r)
        assert len(strings) >= 4


def test_log():
    l = UserLog("wants_to_join", 1, 1, "my_name")
    assert len(l.as_dict()) == 5


def test_dialog():
    fake_extractor = lambda state: print(state)
    dial = Dialog(0, 0, Questionnaire("intro", ["q1"], "outro"), fake_extractor)
    dial._next_q()
    for _ in dial.questions:
        dial._next_q("answer")
    assert len(dial.answers) == len(dial.questions)


def test_dialog_manager():
    q = Questionnaire("intro", ["q1"], "outro")
    fake_extractor = lambda state: print(f"Extractor reporting about {state}")
    dialog = Dialog(1, 1, q, fake_extractor)
    manager = DialogManager()

    manager.add(1, dialog)
    assert 1 in manager

    conv = manager[1]
    assert conv

    if isinstance(conv, Dialog):
        conv.take_reply()
        for _ in conv.questions:
            conv.take_reply("answer")
        assert conv.done
        assert len(conv.questions) == 1


def test_questionnaire_from_db():
    d = {
        "questionnaire": {
            "intro": "Intro. This is my intro.",
            "questions": ["Q1. This is a question.", "Q2.This is another question."],
            "outro": "Outro. This is the outro.",
        }
    }

    settings = Settings(d)
    assert hasattr(settings, "questionnaire")

    questionnaire = settings.questionnaire
    assert questionnaire

    rendered = questionnaire.render()
    print(rendered)
    assert rendered
