# 文件说明：生产 Agent Prompt 的精确版本引用。
from functools import lru_cache

from app.core.config import get_settings
from app.prompts.catalog import PromptCatalog
from app.prompts.schema import LoadedPrompt, PromptReference

REQUIREMENT_PARSER_SYSTEM = PromptReference(
    agent="requirement-parser",
    prompt_id="system",
    version="1.1.0",
)
RESEARCH_PLANNER_TOOL_SELECTION = PromptReference(
    agent="research-planner",
    prompt_id="tool-selection",
    version="1.0.0",
)
ITINERARY_COMPOSER_SYSTEM = PromptReference(
    agent="itinerary-composer",
    prompt_id="system",
    version="1.0.0",
)
TRAVEL_CHAT_INTENT_ROUTER = PromptReference(
    agent="travel-chat",
    prompt_id="intent-router",
    version="1.3.0",
)
TRAVEL_CHAT_ANSWER = PromptReference(
    agent="travel-chat",
    prompt_id="answer",
    version="1.0.0",
)


@lru_cache
def default_prompt_catalog() -> PromptCatalog:
    return PromptCatalog(get_settings().prompts_root)


def load_prompt(reference: PromptReference) -> LoadedPrompt:
    return default_prompt_catalog().get(reference)
