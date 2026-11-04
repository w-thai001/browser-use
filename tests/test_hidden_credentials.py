import pytest

from browser_use.agent.hidden_credentials import HiddenCredential, HiddenCredentialsIngestor


def test_ingest_from_env_and_file_precedence(tmp_path):
	file_path = tmp_path / 'secret.txt'
	file_path.write_text('file-secret\n', encoding='utf-8')

	ingestor = HiddenCredentialsIngestor(
		credentials=[
			HiddenCredential(
				placeholder='api_key',
				env_var='API_KEY',
				file_path=file_path,
			)
		]
	)

	result = ingestor.ingest(environ={'API_KEY': 'env-secret'})

	assert result == {'api_key': 'env-secret'}


def test_ingest_from_file_when_env_missing(tmp_path):
	file_path = tmp_path / 'secret.txt'
	file_path.write_text('file-secret\n', encoding='utf-8')

	ingestor = HiddenCredentialsIngestor(
		credentials=[
			HiddenCredential(
				placeholder='api_key',
				file_path=file_path,
			)
		]
	)

	result = ingestor.ingest(environ={})

	assert result == {'api_key': 'file-secret'}


def test_masked_values_hide_content(tmp_path):
	file_path = tmp_path / 'secret.txt'
	file_path.write_text('abcd1234', encoding='utf-8')

	ingestor = HiddenCredentialsIngestor(
		credentials=[HiddenCredential(placeholder='token', file_path=file_path)],
		mask_char='•',
		mask_keep_last=3,
	)

	masked = ingestor.masked(environ={})

	assert masked['token'] == '•••••234'


def test_missing_required_credentials_raise():
	ingestor = HiddenCredentialsIngestor(
		credentials=[HiddenCredential(placeholder='token', env_var='MISSING_ENV')],
	)

	with pytest.raises(ValueError):
		ingestor.ingest(environ={})


def test_optional_credentials_are_skipped_when_missing():
	ingestor = HiddenCredentialsIngestor(
		credentials=[
			HiddenCredential(
				placeholder='token',
				env_var='MISSING_ENV',
				required=False,
			)
		]
	)

	result = ingestor.ingest(environ={})

	assert result == {}
