"""Garmin Connect client bootstrap."""

from __future__ import annotations

from garminconnect import Garmin

from .config import ProjectConfig, read_password


def build_client(config: ProjectConfig) -> Garmin:
    """Authenticate a Garmin Connect client for project workflows.

    Args:
        config: Resolved project configuration with credentials and token paths.

    Returns:
        An authenticated :class:`garminconnect.Garmin` client.

    Raises:
        RuntimeError: If Garmin requests MFA instead of completing the login
            flow non-interactively.
    """

    config.token_store.parent.mkdir(parents=True, exist_ok=True)
    client = Garmin(email=config.email, password=read_password(config))
    needs_mfa, _legacy_token = client.login(tokenstore=str(config.token_store))
    if needs_mfa is not None:
        raise RuntimeError("Garmin login requested MFA; complete login interactively.")
    return client
