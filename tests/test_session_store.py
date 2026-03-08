# input: mindclaw.knowledge.session
# output: SessionStore 测试
# pos: 验证 JSONL 持久化和整合指针
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.knowledge.session import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(data_dir=tmp_path)


def test_append_and_load(store, tmp_path):
    """Append messages then load them back."""
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    store.append("cli:local", messages)
    loaded, total = store.load("cli:local")
    assert len(loaded) == 2
    assert total == 2
    assert loaded[0]["role"] == "user"
    assert loaded[1]["content"] == "hi there"


def test_load_empty_session(store):
    """Loading a non-existent session returns empty list."""
    loaded, total = store.load("cli:nonexistent")
    assert loaded == []
    assert total == 0


def test_append_multiple_times(store):
    """Multiple appends accumulate messages."""
    store.append("cli:local", [{"role": "user", "content": "msg1"}])
    store.append("cli:local", [{"role": "assistant", "content": "reply1"}])
    store.append("cli:local", [{"role": "user", "content": "msg2"}])
    loaded, total = store.load("cli:local")
    assert len(loaded) == 3
    assert total == 3


def test_mark_consolidated_and_load(store):
    """After consolidation, load only returns unconsolidated messages."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
    store.append("cli:local", messages)
    store.mark_consolidated("cli:local", pointer=3)
    loaded, total = store.load("cli:local")
    assert len(loaded) == 2  # msg3, msg4
    assert total == 5
    assert loaded[0]["content"] == "msg3"


def test_mark_consolidated_twice(store):
    """Second consolidation moves pointer further."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    store.append("cli:local", messages)
    store.mark_consolidated("cli:local", pointer=3)
    store.mark_consolidated("cli:local", pointer=7)
    loaded, total = store.load("cli:local")
    assert len(loaded) == 3  # msg7, msg8, msg9
    assert total == 10


def test_session_key_to_filename(store):
    """Session key is sanitized for filesystem use."""
    store.append("telegram:12345", [{"role": "user", "content": "hi"}])
    loaded, total = store.load("telegram:12345")
    assert len(loaded) == 1


def test_load_returns_messages_for_consolidation(store):
    """load_for_consolidation returns messages in the consolidation window."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert len(to_consolidate) == 15
    assert to_consolidate[0]["content"] == "msg0"
    assert to_consolidate[-1]["content"] == "msg14"


def test_load_for_consolidation_with_existing_pointer(store):
    """Consolidation window starts after previous pointer."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)
    store.mark_consolidated("cli:local", pointer=5)
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert len(to_consolidate) == 10
    assert to_consolidate[0]["content"] == "msg5"
    assert to_consolidate[-1]["content"] == "msg14"


def test_load_for_consolidation_not_enough_messages(store):
    """If not enough messages beyond keep_recent, return empty."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(8)]
    store.append("cli:local", messages)
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert to_consolidate == []
