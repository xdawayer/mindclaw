# input: mindclaw.llm.classifier, mindclaw.config.schema
# output: 模型路由测试
# pos: 意图分类 + 模型路由集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md


from mindclaw.config.schema import AgentConfig, MindClawConfig, ModelRoutingConfig
from mindclaw.llm.classifier import classify_intent

# ── ModelRoutingConfig ──


class TestModelRoutingConfig:
    def test_default_disabled(self):
        cfg = ModelRoutingConfig()
        assert cfg.enabled is False

    def test_enabled_with_categories(self):
        cfg = ModelRoutingConfig(
            enabled=True,
            categories={"planning": "openai/gpt-5.4"},
        )
        assert cfg.enabled is True
        assert cfg.categories["planning"] == "openai/gpt-5.4"

    def test_agent_config_has_routing(self):
        agent = AgentConfig(
            model_routing=ModelRoutingConfig(enabled=True),
        )
        assert agent.model_routing.enabled is True


# ── classify_intent ──


class TestClassifyIntent:
    def test_planning_keywords(self):
        assert classify_intent("帮我规划一下项目架构") == "planning"
        assert classify_intent("分析一下这个方案的优缺点") == "planning"
        assert classify_intent("设计一个系统架构") == "planning"
        assert classify_intent("对比这两个方案") == "planning"

    def test_coding_keywords(self):
        assert classify_intent("写一个函数来处理数据") == "coding"
        assert classify_intent("帮我debug这个问题") == "coding"
        assert classify_intent("重构这段代码") == "coding"
        assert classify_intent("实现一个API接口") == "coding"
        assert classify_intent("fix this bug") == "coding"

    def test_writing_keywords(self):
        assert classify_intent("写一篇关于AI的文章") == "writing"
        assert classify_intent("帮我润色这段文案") == "writing"
        assert classify_intent("翻译这段话成英文") == "writing"
        assert classify_intent("总结一下这篇报告") == "writing"

    def test_search_keywords(self):
        assert classify_intent("搜索一下最新的AI新闻") == "search"
        assert classify_intent("查一下天气") == "search"
        assert classify_intent("帮我找一下这个资料") == "search"

    def test_general_fallback(self):
        assert classify_intent("你好") == "general"
        assert classify_intent("谢谢") == "general"
        assert classify_intent("今天怎么样") == "general"

    def test_hashtag_override(self):
        """User can force category with #tag prefix."""
        assert classify_intent("#planning 随便聊聊") == "planning"
        assert classify_intent("#coding 帮我看看") == "coding"
        assert classify_intent("#writing 你好") == "writing"
        assert classify_intent("#search 你好") == "search"

    def test_empty_string(self):
        assert classify_intent("") == "general"

    def test_english_keywords(self):
        assert classify_intent("refactor this module") == "coding"
        assert classify_intent("write an article about Python") == "writing"
        assert classify_intent("search for React best practices") == "search"
        assert classify_intent("plan the migration strategy") == "planning"

    def test_short_keyword_word_boundary(self):
        """Short English keywords should not match as substrings."""
        # "fix" should not match "prefix" or "Netflix"
        assert classify_intent("add a prefix to the string") == "general"
        # "api" should not match "capital"
        assert classify_intent("what is the capital of France") == "general"
        # "code" should not match "barcode"
        assert classify_intent("scan the barcode") == "general"
        # But exact word matches should still work
        assert classify_intent("fix this bug") == "coding"
        assert classify_intent("call the api") == "coding"
        assert classify_intent("find the document") == "search"


# ── LLMRouter model routing integration ──


class TestRouterModelRouting:
    def test_resolve_model_with_routing(self):
        from mindclaw.llm.router import LLMRouter

        config = MindClawConfig(
            agent=AgentConfig(
                default_model="openai/gpt-4o",
                model_routing=ModelRoutingConfig(
                    enabled=True,
                    categories={
                        "coding": "openai/gpt-5.3-codex",
                        "planning": "openai/gpt-5.4",
                    },
                ),
            ),
        )
        router = LLMRouter(config)
        assert router.resolve_model_for_task("coding") == "openai/gpt-5.3-codex"
        assert router.resolve_model_for_task("planning") == "openai/gpt-5.4"
        assert router.resolve_model_for_task("general") == "openai/gpt-4o"
        assert router.resolve_model_for_task("unknown") == "openai/gpt-4o"

    def test_resolve_model_routing_disabled(self):
        from mindclaw.llm.router import LLMRouter

        config = MindClawConfig(
            agent=AgentConfig(
                default_model="openai/gpt-4o",
                model_routing=ModelRoutingConfig(enabled=False),
            ),
        )
        router = LLMRouter(config)
        assert router.resolve_model_for_task("coding") == "openai/gpt-4o"
        assert router.resolve_model_for_task("planning") == "openai/gpt-4o"
