import os

from jibeon_cad_tool.env import load_env


def test_load_env_sets_environment_variable_from_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_JIBEON_VAR=hello\n", encoding="utf-8")
    monkeypatch.delenv("TEST_JIBEON_VAR", raising=False)

    load_env(dotenv_path=env_file)

    assert os.environ["TEST_JIBEON_VAR"] == "hello"
    del os.environ["TEST_JIBEON_VAR"]


def test_load_env_does_not_override_existing_environment_variable(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_JIBEON_VAR=from_file\n", encoding="utf-8")
    monkeypatch.setenv("TEST_JIBEON_VAR", "from_shell")

    load_env(dotenv_path=env_file)

    assert os.environ["TEST_JIBEON_VAR"] == "from_shell"
