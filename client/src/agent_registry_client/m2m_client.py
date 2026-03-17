"""
Machine-to-Machine Agent Registry Client (API Key auth)

Lightweight client for agents to self-register and discover other agents
without AWS IAM credentials. Uses API Key authentication.
"""
import json
import time
import random
import logging
from typing import List, Optional, Dict, Any

import requests

from .exceptions import (
    AgentRegistryError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError,
)
from .models import AgentListResponse, SearchResult

logger = logging.getLogger(__name__)


class M2MClient:
    """Client for agent-to-registry communication using API Key auth."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
        timeout: int = 30,
    ):
        """
        Args:
            api_url: M2M API Gateway URL (e.g. https://xxx.execute-api.eu-west-1.amazonaws.com/prod)
            api_key: API Key value for x-api-key header
            max_retries: Max retry attempts for failed requests
            retry_backoff_factor: Backoff multiplier for retries
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.timeout = timeout

    def _make_request(
        self, method: str, path: str, body: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Any:
        url = f"{self.api_url}{path}"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
        kwargs: Dict[str, Any] = {"headers": headers, "timeout": self.timeout}

        if body:
            kwargs["json"] = body
        if params:
            kwargs["params"] = params

        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = getattr(requests, method.lower())(url, **kwargs)

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 400:
                    err = resp.json().get("error", {})
                    raise ValidationError(err.get("message", "Bad request"))
                elif resp.status_code in (401, 403):
                    raise AuthenticationError("Invalid or missing API key")
                elif resp.status_code == 404:
                    err = resp.json().get("error", {})
                    raise NotFoundError(err.get("message", "Not found"))
                elif resp.status_code >= 500:
                    err_msg = resp.text
                    try:
                        err_msg = resp.json().get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    raise ServerError(err_msg)
                else:
                    raise AgentRegistryError(f"Unexpected status {resp.status_code}: {resp.text}")

            except (ServerError, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = (2**attempt) * self.retry_backoff_factor + random.uniform(0, 0.1)
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {e}")
                    time.sleep(delay)
                    continue
                raise AgentRegistryError(f"Failed after {self.max_retries} retries: {e}") from e

            except (ValidationError, NotFoundError, AuthenticationError):
                raise
            except requests.exceptions.RequestException as e:
                raise AgentRegistryError(f"Request failed: {e}") from e

        raise AgentRegistryError("Request failed after all retries") from last_exc

    # --- Agent CRUD ---

    def register_agent(self, agent_data: Dict[str, Any]) -> str:
        """Register a new agent. Returns agent_id."""
        resp = self._make_request("POST", "/agents", body=agent_data)
        agent_id = resp.get("agent_id")
        if not agent_id:
            raise AgentRegistryError("Response missing agent_id")
        logger.info(f"Registered agent: {agent_id}")
        return agent_id

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent by ID."""
        resp = self._make_request("GET", f"/agents/{agent_id}")
        return resp.get("agent", resp)

    def list_agents(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List agents with pagination."""
        return self._make_request("GET", "/agents", params={"limit": limit, "offset": offset})

    def search_agents(
        self, text: Optional[str] = None, skills: Optional[List[str]] = None, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search agents by text and/or skills."""
        if not text and not skills:
            raise ValidationError("Provide text or skills")
        params: Dict[str, Any] = {"top_k": top_k}
        if text:
            params["text"] = text
        if skills:
            params["skills"] = ",".join(skills)
        resp = self._make_request("GET", "/agents/search", params=params)
        return resp if isinstance(resp, list) else resp.get("results", [])

    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an agent (partial update)."""
        resp = self._make_request("PUT", f"/agents/{agent_id}", body=update_data)
        return "success" in resp.get("message", "").lower()

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        resp = self._make_request("DELETE", f"/agents/{agent_id}")
        logger.info(f"Deleted agent: {agent_id}")
        return "success" in resp.get("message", "").lower()

    def update_health(self, agent_id: str) -> bool:
        """Send health heartbeat."""
        resp = self._make_request("POST", f"/agents/{agent_id}/health")
        return "success" in resp.get("message", "").lower()
