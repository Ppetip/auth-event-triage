"""Static, per-host ingestion credentials with overlapping-key rotation.

Secrets are supplied through the deployment environment, never persisted in SQLite.
A server restart applies changes to the credential registry.
"""
import hmac
import json
import re

from .core import HOST_RE

TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{32,128}$')
MAX_AGENTS = 128
MAX_KEYS_PER_AGENT = 3


def parse_agent_tokens(value, ingest_key, read_key):
    """Parse an optional JSON mapping of host IDs to one or more bearer keys.

    The JSON representation is {"host-1": ["current-key", "next-key"]}.
    Multiple keys per host permit a restart-based, overlapping-key rotation.
    """
    if not value:
        return {}
    try:
        config = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('SENTINEL_AGENT_TOKENS_JSON must be valid JSON') from exc
    if not isinstance(config, dict) or len(config) > MAX_AGENTS:
        raise ValueError('agent credentials must be a JSON object with at most 128 hosts')
    used = {key for key in (ingest_key, read_key) if key}
    agents = {}
    for host, keys in config.items():
        if not isinstance(host, str) or host == 'legacy' or not HOST_RE.fullmatch(host):
            raise ValueError('invalid agent host identifier')
        if isinstance(keys, str):
            keys = [keys]
        if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_KEYS_PER_AGENT:
            raise ValueError('each agent needs 1 to 3 credentials')
        for key in keys:
            if not isinstance(key, str) or not TOKEN_RE.fullmatch(key):
                raise ValueError('agent tokens must be 32-128 URL-safe characters')
            if key in used:
                raise ValueError('duplicate or cross-role agent token')
            used.add(key)
        agents[host] = tuple(keys)
    return agents


class IngestCredentials:
    """Resolve bearer credentials to host identities without storing them."""

    def __init__(self, ingest_key, read_key, agents):
        if not read_key or (not ingest_key and not agents) or ingest_key == read_key:
            raise ValueError('set a reader token and distinct ingestion credentials')
        self._legacy = ingest_key
        self._agents = tuple((host, key) for host, keys in agents.items() for key in keys)

    def identify(self, authorization):
        if not isinstance(authorization, str) or not authorization.startswith('Bearer '):
            return None
        # Compare every configured key, even if one matches, to avoid a
        # key-position timing oracle. Deployment should still use loopback/TLS.
        legacy_match = bool(self._legacy) and hmac.compare_digest(authorization, 'Bearer ' + self._legacy)
        matched_host = 'legacy' if legacy_match else None
        for host, key in self._agents:
            if hmac.compare_digest(authorization, 'Bearer ' + key):
                matched_host = host
        return matched_host
