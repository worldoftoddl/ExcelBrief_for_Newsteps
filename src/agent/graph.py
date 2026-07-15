"""ExcelBrief 에이전트 그래프 — langgraph.json 진입점.

모델 라우팅: config["configurable"]["model"] 값으로 요청마다 모델을 결정한다.
  - "anthropic:<model-id>"  → 상용 Anthropic API (기본)
  - "local:<model-name>"    → OpenAI 호환 로컬 서버 (vLLM/Ollama)
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig

from agent.mcp_client import get_standards_tools
from agent.prompts import SYSTEM_PROMPT
from agent.tools.excel import EXCEL_TOOLS

load_dotenv()

DEFAULT_MODEL = "anthropic:claude-sonnet-5"


def resolve_model(spec: str):
    """모델 문자열 접두사로 제공자를 분기한다. 라우트 추가는 이 함수만 수정."""
    if spec.startswith("local:"):
        return init_chat_model(
            f"openai:{spec.removeprefix('local:')}",
            base_url=os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("LOCAL_LLM_API_KEY", "not-needed"),
        )
    return init_chat_model(spec)


async def graph(config: RunnableConfig):
    """요청 config를 받아 에이전트를 조립하는 팩토리 (langgraph 서버가 호출)."""
    model_spec = (config.get("configurable") or {}).get("model", DEFAULT_MODEL)
    tools = EXCEL_TOOLS + list(await get_standards_tools())
    return create_agent(
        model=resolve_model(model_spec),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
