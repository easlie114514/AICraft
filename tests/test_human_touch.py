"""人味（Human Touch）功能单元测试"""
import pytest
from src.core.role_loader import (
    build_human_touch_prompt,
    load_human_touch_config,
    HUMAN_TOUCH_LEVELS,
)


class TestBuildHumanTouchPrompt:
    """测试 build_human_touch_prompt 函数"""

    def test_level_1_contains_core_concepts(self):
        prompt = build_human_touch_prompt(1)
        assert prompt is not None
        assert "口语化" in prompt
        assert "机器人感" in prompt

    def test_level_2_includes_level_1(self):
        l1 = build_human_touch_prompt(1)
        l2 = build_human_touch_prompt(2)
        assert l2 is not None
        assert l1 in l2

    def test_level_3_includes_level_2(self):
        l2 = build_human_touch_prompt(2)
        l3 = build_human_touch_prompt(3)
        assert l3 is not None
        assert l2 in l3

    def test_level_3_includes_level_1(self):
        l1 = build_human_touch_prompt(1)
        l3 = build_human_touch_prompt(3)
        assert l3 is not None
        assert l1 in l3

    def test_invalid_level_returns_none(self):
        assert build_human_touch_prompt(0) is None
        assert build_human_touch_prompt(4) is None
        assert build_human_touch_prompt(-1) is None

    def test_level_3_contains_temperament(self):
        """用户强调的"有脾气"必须在 L3 中包含"""
        prompt = build_human_touch_prompt(3)
        assert prompt is not None
        assert "脾气" in prompt

    def test_all_valid_levels_return_string(self):
        for level in HUMAN_TOUCH_LEVELS:
            prompt = build_human_touch_prompt(level)
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestLoadHumanTouchConfig:
    """测试 load_human_touch_config 函数"""

    def test_default_config_for_nonexistent_role(self):
        config = load_human_touch_config("this_role_does_not_exist")
        assert config["enabled"] is False
        assert config["level"] == 1

    def test_config_has_expected_keys(self):
        config = load_human_touch_config("nonexistent")
        assert "enabled" in config
        assert "level" in config
        assert isinstance(config["enabled"], bool)
        assert isinstance(config["level"], int)
