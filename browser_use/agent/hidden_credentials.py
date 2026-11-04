from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class HiddenCredential(BaseModel):
	placeholder: str = Field(..., description='Placeholder name exposed to the LLM')
	env_var: Optional[str] = Field(default=None, description='Environment variable to read the value from')
	file_path: Optional[Path] = Field(default=None, description='File path that contains the secret value')
	value: Optional[SecretStr] = Field(default=None, description='Directly supplied secret value')
	description: Optional[str] = Field(default=None, description='Human readable hint about what the secret is for')
	required: bool = Field(default=True, description='Whether the credential must be present')

	@model_validator(mode='after')
	def validate_source(self) -> 'HiddenCredential':
		"""Ensure at least one source is configured."""
		if not any([self.env_var, self.file_path, self.value]):
			raise ValueError('HiddenCredential must define env_var, file_path, or value.')
		return self


class HiddenCredentialsIngestor(BaseModel):
	"""
	Collect credentials from different sources once and pass placeholders to the LLM without exposing raw values.

	Precedence order for loading values:
	1. Direct ``value`` (if provided)
	2. Environment variable (``env_var``)
	3. File at ``file_path``
	"""

	credentials: list[HiddenCredential] = Field(default_factory=list)
	mask_char: str = Field(default='*', description='Character used for masking in debug views')
	mask_keep_last: int = Field(default=4, description='Number of trailing characters to keep when masking')

	@field_validator('mask_keep_last')
	@classmethod
	def validate_mask_keep_last(cls, value: int) -> int:
		if value < 0:
			raise ValueError('mask_keep_last must be >= 0')
		return value

	def ingest(self, environ: Optional[Mapping[str, str]] = None) -> dict[str, str]:
		"""Return a mapping of placeholder -> secret value after loading all configured credentials."""
		env = environ if environ is not None else os.environ
		ingested: dict[str, str] = {}
		missing_required: list[str] = []

		for credential in self.credentials:
			try:
				value = self._resolve_value(credential, env)
			except FileNotFoundError as exc:
				if credential.required:
					raise ValueError(
						f'Credential file for placeholder "{credential.placeholder}" not found at "{exc.filename}".'
					) from exc
				value = None

			if value is None:
				if credential.required:
					missing_required.append(credential.placeholder)
				continue

			ingested[credential.placeholder] = value

		if missing_required:
			raise ValueError(f'Missing credentials for placeholders: {", ".join(sorted(missing_required))}')

		return ingested

	def masked(self, environ: Optional[Mapping[str, str]] = None) -> dict[str, str]:
		"""
		Return a redacted mapping (placeholder -> masked value) for debugging or logging without exposing secrets.
		Secrets that cannot be resolved are omitted.
		"""
		env = environ if environ is not None else os.environ
		masked_values: dict[str, str] = {}

		for credential in self.credentials:
			try:
				value = self._resolve_value(credential, env)
			except FileNotFoundError:
				continue

			if value is None:
				continue

			masked_values[credential.placeholder] = self._mask_value(value)

		return masked_values

	def placeholder_names(self) -> list[str]:
		"""Return all placeholder names tracked by the ingestor."""
		return [credential.placeholder for credential in self.credentials]

	def _resolve_value(self, credential: HiddenCredential, environ: Mapping[str, str]) -> Optional[str]:
		if credential.value:
			return credential.value.get_secret_value().strip()

		if credential.env_var and credential.env_var in environ:
			val = environ.get(credential.env_var)
			if val is not None:
				return str(val).strip()

		if credential.file_path:
			path = credential.file_path.expanduser()
			if path.exists():
				return path.read_text(encoding='utf-8').strip()
			if credential.required:
				raise FileNotFoundError(path)

		return None

	def _mask_value(self, value: str) -> str:
		if not value:
			return ''

		keep = min(self.mask_keep_last, len(value))
		mask_length = max(len(value) - keep, 0)
		return f'{self.mask_char * mask_length}{value[-keep:]}' if keep else self.mask_char * mask_length
