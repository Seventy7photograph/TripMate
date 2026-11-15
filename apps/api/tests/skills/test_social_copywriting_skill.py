# 文件说明：后端自动化测试：social-copywriting Skill。
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.skills.executor import SkillContext, SkillExecutor
from app.skills.production import SocialCopywritingInput, production_skill_handlers
from app.skills.registry import load_configured_registry
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry


async def test_social_copy_uses_confirmed_facts_and_never_publishes() -> None:
    context = ToolContext(
        runner=ToolRunner(
            max_calls=1,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools=set(),
        provider_permissions=set(),
        owner_id=uuid4(),
    )
    tools = ToolRegistry()
    skills = load_configured_registry(Settings(app_env="test"))
    manifest = skills.get("social-copywriting")
    handlers = production_skill_handlers(tools, context)

    result = await SkillExecutor().execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[manifest.name],
        ),
        SocialCopywritingInput(
            destination="泉州",
            platform="xiaohongshu",
            tone="quiet",
            confirmed_facts=["开元寺开放时间以现场公告为准"],
            trip_days=3,
        ),
    )

    assert result.output.facts_used == ["开元寺开放时间以现场公告为准"]
    assert result.output.auto_published is False
    assert result.output.evidence_links == []


async def test_social_copy_allows_unknown_trip_duration() -> None:
    context = ToolContext(
        runner=ToolRunner(
            max_calls=1,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools=set(),
        provider_permissions=set(),
        owner_id=uuid4(),
    )
    skills = load_configured_registry(Settings(app_env="test"))
    manifest = skills.get("social-copywriting")
    tools = ToolRegistry()

    result = await SkillExecutor().execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=production_skill_handlers(tools, context)[manifest.name],
        ),
        SocialCopywritingInput(
            destination="泉州",
            platform="wechat_moments",
            tone="quiet",
            confirmed_facts=[],
            trip_days=None,
        ),
    )

    assert result.output.title.startswith("泉州")
