from __future__ import annotations

from app.utils.state_path_utils import read_state_value, state_path_exists, write_state_value


def test_read_state_value_supports_nested_dict_and_list_paths() -> None:
    state = {
        "form": {
            "customer": {
                "name": "张三",
                "phones": [{"number": "13800000000"}],
            }
        }
    }

    assert read_state_value(state, "/form/customer/name") == "张三"
    assert read_state_value(state, "/form/customer/phones/0/number") == "13800000000"
    assert read_state_value(state, "/form/customer/missing") is None


def test_write_state_value_builds_missing_nested_objects() -> None:
    state: dict[str, object] = {}

    write_state_value(state, "/form/customer/name", "李四")

    assert state == {"form": {"customer": {"name": "李四"}}}


def test_state_path_exists_supports_list_indices() -> None:
    state = {"form": {"phones": [{"number": "13800000000"}], "nullable": None}}

    assert state_path_exists(state, "/form/phones/0/number") is True
    assert state_path_exists(state, "/form/phones/1/number") is False
    assert state_path_exists(state, "/form/nullable") is True
