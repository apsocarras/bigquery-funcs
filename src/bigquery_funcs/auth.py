import os
from dataclasses import dataclass, fields
from pathlib import Path

import google.cloud.secretmanager as secretmanager
from dotenv import load_dotenv
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account

from ._types import SecretContextType


class MissingSecretsError(Exception):
    pass


def load_env_secrets(
    context: SecretContextType,
    env_path: str | Path | None = None,
    project_id: str | None = None,
    service_account_key_path: str | Path | None = None,
    enforce_env_var: bool = False,
) -> None:
    """Load env vars either from a local .env or google cloud secrets manager (GCSM)

    Args:
        context (Literal['local', 'google_secrets_manager']): Whether to use local .env or GCSM. Defaults to 'local'.
        env_path (Optional[Union[str, Path]], optional): Path to local .env (used when context is 'local'). Defaults to os.path.join("_local", '.env').
        project_id (Optional[str], optional): Google Cloud project ID for the secrets manager (used when context is 'google_secrets_manager'). Defaults to None.

    Raises:
        ValueError: .env not provided when context == 'local'.
        FileNotFoundError: If .env file not found at the path for 'local' context.
        ValueError: Invalid 'context' value.
        ValueError: If Google Cloud project_id is missing for 'google_secrets_manager' context.
        ValueError: If A.) GOOGLE_APPLICATION_CREDENTIALS .env variable, and B.) service_account_key_path, are missing for 'google_secrets_manager' context.
        ValueError: If Google Cloud authentication fails.
    """
    assert context in ("local", "google_secrets_manager"), (
        f"Invalid value for 'context': {context}"
    )
    match context:
        case "local":
            if env_path is None:
                raise ValueError('Must provide valid .env path if context == "local"')
            env_path = Path(env_path)
            if not env_path.exists():
                raise FileNotFoundError(f".env file not found at {env_path}")
            _ = load_dotenv(env_path)
        case "google_secrets_manager":
            if project_id is None:
                raise ValueError(
                    'Must provide valid project_id if context == "google_secrets_manager"'
                )
            try:
                # Trying to load env variable or set .json key
                if service_account_key_path:
                    credentials = service_account.Credentials.from_service_account_file(  # pyright: ignore[reportUnknownMemberType]
                        service_account_key_path
                    )
                    client = secretmanager.SecretManagerServiceClient(
                        credentials=credentials
                    )
                else:  # from env
                    if enforce_env_var:
                        if not (os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)):
                            raise MissingSecretsError(
                                "Must have GOOGLE_APPLICATION_CREDENTIALS env var if not passing 'service_account_key_path'"
                            )
                    client = secretmanager.SecretManagerServiceClient()

                parent = f"projects/{project_id}"

                secrets = client.list_secrets(parent=parent)  # pyright: ignore[reportUnknownMemberType]
                for secret in secrets:
                    secret_name = secret.name.split("/")[-1]
                    secret_version = client.access_secret_version(  # pyright: ignore[reportUnknownMemberType]
                        name=f"{secret.name}/versions/latest"
                    )
                    secret_payload = secret_version.payload.data.decode("UTF-8")
                    os.environ[secret_name] = secret_payload  # Set environment variable

            except DefaultCredentialsError:
                raise ValueError(
                    "Could not authenticate with Google Cloud. Ensure credentials are set up correctly."
                )


@dataclass
class SecretSet:
    @classmethod
    def from_env(
        cls,
        secret_context: SecretContextType,
        env_path: str | Path | None = None,
        project_id: str | None = None,
        service_account_key_path: str | Path | None = None,
    ):
        load_env_secrets(
            context=secret_context,
            env_path=env_path,
            project_id=project_id,
            service_account_key_path=service_account_key_path,
        )
        env_context = {}
        for field in fields(cls):
            if field.name.startswith("_"):
                continue
            env_context[field.name] = os.getenv(field.name, None)
        missing_vals = [k for k, v in env_context.items() if v is None]
        if missing_vals:
            raise ValueError(f"Missing environment secrets: {missing_vals}")

        return cls(**env_context)


@dataclass
class ApplicationCredentials(SecretSet):
    GOOGLE_APPLICATION_CREDENTIALS: str
