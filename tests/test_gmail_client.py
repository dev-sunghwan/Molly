import config
import gmail_client


def test_gmail_client_uses_readonly_scope():
    assert gmail_client.SCOPES == ["https://www.googleapis.com/auth/gmail.readonly"]


def test_gmail_client_uses_separate_token_path():
    assert config.GMAIL_TOKEN_PATH.name == "gmail_token.json"
    assert config.GMAIL_TOKEN_PATH != config.TOKEN_PATH
    assert config.GMAIL_CREDENTIALS_PATH == config.CREDENTIALS_PATH
