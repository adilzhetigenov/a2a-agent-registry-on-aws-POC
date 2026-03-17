"""
Agent Lifecycle Manager

Handles automatic registration, heartbeat, and deregistration.
Designed to be used in agent startup/shutdown hooks on EKS.

Usage:
    lifecycle = AgentLifecycle(
        api_url="https://xxx.execute-api.eu-west-1.amazonaws.com/prod",
        api_key="your-api-key",
        agent_config={
            "name": "MyAgent",
            "description": "Does useful things",
            "version": "1.0.0",
            "url": "https://my-agent.eks.local/api",
            "skills": ["python", "data-analysis"],
        },
        heartbeat_interval=30,
    )

    # Start (registers + begins heartbeat thread)
    lifecycle.start()

    # ... agent does its work ...

    # Stop (stops heartbeat + deregisters)
    lifecycle.stop()

    # Or use as context manager:
    with lifecycle:
        # agent does its work
        pass
"""
import logging
import signal
import threading
import time
from typing import Any, Dict, List, Optional

from .m2m_client import M2MClient

logger = logging.getLogger(__name__)


class AgentLifecycle:
    """Manages agent registration, heartbeat, and deregistration."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        agent_config: Dict[str, Any],
        heartbeat_interval: int = 30,
        register_signals: bool = True,
    ):
        """
        Args:
            api_url: M2M API Gateway URL
            api_key: API Key value
            agent_config: Agent card data (name, description, version, url, skills, etc.)
            heartbeat_interval: Seconds between heartbeats (0 to disable)
            register_signals: Register SIGTERM/SIGINT handlers for graceful shutdown
        """
        self.client = M2MClient(api_url=api_url, api_key=api_key)
        self.agent_config = agent_config
        self.heartbeat_interval = heartbeat_interval
        self.agent_id: Optional[str] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if register_signals:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()

    def _heartbeat_loop(self) -> None:
        """Background thread that sends periodic heartbeats."""
        while not self._stop_event.is_set():
            if self.agent_id:
                try:
                    self.client.update_health(self.agent_id)
                    logger.debug(f"Heartbeat sent for {self.agent_id}")
                except Exception as e:
                    logger.warning(f"Heartbeat failed: {e}")
            self._stop_event.wait(self.heartbeat_interval)

    def start(self) -> str:
        """Register agent and start heartbeat. Returns agent_id."""
        self.agent_id = self.client.register_agent(self.agent_config)
        logger.info(f"Agent registered: {self.agent_id}")

        if self.heartbeat_interval > 0:
            self._stop_event.clear()
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, daemon=True, name="agent-heartbeat"
            )
            self._heartbeat_thread.start()
            logger.info(f"Heartbeat started (every {self.heartbeat_interval}s)")

        return self.agent_id

    def stop(self) -> None:
        """Stop heartbeat and deregister agent."""
        self._stop_event.set()

        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
            logger.info("Heartbeat stopped")

        if self.agent_id:
            try:
                self.client.delete_agent(self.agent_id)
                logger.info(f"Agent deregistered: {self.agent_id}")
            except Exception as e:
                logger.warning(f"Deregistration failed: {e}")
            self.agent_id = None

    def search(
        self, text: Optional[str] = None, skills: Optional[List[str]] = None, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for other agents."""
        return self.client.search_agents(text=text, skills=skills, top_k=top_k)

    def __enter__(self) -> "AgentLifecycle":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
