import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AppConfig:
    llm_gateway_host: str
    llm_gateway_token: str
    llm_model: str
    serper_api_key: str
    serper_base_url: str
    serper_scrape_base_url: str
    agent_max_turns: int
    flask_host: str
    flask_port: int

    @property
    def llm_base_url(self) -> str:
        host = self.llm_gateway_host.strip().rstrip("/")
        if host.endswith("/v1"):
            return host
        return f"{host}/v1"


def load_config() -> AppConfig:
    # Always load the .env file colocated with this module to avoid cwd/reloader differences.
    dotenv_path = Path(__file__).resolve().with_name(".env")
    load_dotenv(dotenv_path=dotenv_path, override=True)
    return AppConfig(
        llm_gateway_host=os.getenv("LLM_GATEWAY_HOST", "").strip(),
        llm_gateway_token=os.getenv("LLM_GATEWAY_TOKEN", "").strip(),
        # Default to agent-advoo; agent.py still falls back to /v1/models when needed.
        llm_model=os.getenv("LLM_MODEL", "").strip() or "agent-advoo",
        serper_api_key=os.getenv("SERPER_API_KEY", "").strip(),
        serper_base_url=os.getenv(
            "SERPER_BASE_URL", "https://google.serper.dev"
        ).strip(),
        serper_scrape_base_url=os.getenv(
            "SERPER_SCRAPE_BASE_URL", "https://scrape.serper.dev"
        ).strip(),
        agent_max_turns=int(os.getenv("AGENT_MAX_TURNS", "6")),
        flask_host=os.getenv("FLASK_HOST", "127.0.0.1").strip(),
        flask_port=int(os.getenv("FLASK_PORT", "5000")),
    )
