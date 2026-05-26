import json
from unittest.mock import MagicMock, patch

import pytest

from pipeline.script_gen import generate_script


def _mock_topic(title="Польза магния", brief="для сна"):
    t = MagicMock()
    t.id = 1
    t.title = title
    t.brief = brief
    return t


def _mock_channel(template=None):
    c = MagicMock()
    c.script_prompt_template = template
    return c


def _make_anthropic_response(content: str):
    resp = MagicMock()
    resp.content = [MagicMock(text=content)]
    resp.usage = MagicMock(input_tokens=100, output_tokens=200)
    return resp


VALID_SCRIPT = {
    "title": "Магний и сон #shorts",
    "hook": "Вы знали, что 70% людей испытывают дефицит магния?",
    "body": "Магний участвует в 300 биохимических реакциях...",
    "cta": "А вы принимаете магний?",
    "full_text": "Вы знали что 70%... Магний участвует... А вы принимаете магний?",
    "tags": ["магний", "сон", "здоровье"],
    "description": "Описание видео #магний",
    "broll_keywords": ["sleeping person", "magnesium supplement"],
    "estimated_duration_sec": 70.0,
}


def test_generate_script_success():
    with patch("pipeline.script_gen.anthropic.Anthropic") as MockCls:
        mock_client = MockCls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response(json.dumps(VALID_SCRIPT))

        result = generate_script(_mock_topic(), _mock_channel())

        assert result["title"] == VALID_SCRIPT["title"]
        assert result["hook"] == VALID_SCRIPT["hook"]
        assert isinstance(result["tags"], list)
        assert isinstance(result["broll_keywords"], list)
        assert "_cost_usd" in result
        assert result["_cost_usd"] > 0


def test_generate_script_strips_markdown_fences():
    fenced = f"```json\n{json.dumps(VALID_SCRIPT)}\n```"
    with patch("pipeline.script_gen.anthropic.Anthropic") as MockCls:
        mock_client = MockCls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response(fenced)

        result = generate_script(_mock_topic(), _mock_channel())
        assert result["title"] == VALID_SCRIPT["title"]


def test_generate_script_retries_on_bad_json():
    bad = "not json at all"
    with patch("pipeline.script_gen.anthropic.Anthropic") as MockCls:
        mock_client = MockCls.return_value
        mock_client.messages.create.return_value = _make_anthropic_response(bad)

        from pipeline.errors import PipelineError
        with pytest.raises(PipelineError) as exc_info:
            generate_script(_mock_topic(), _mock_channel())
        assert exc_info.value.step_name == "script_gen"
        # Should have called twice (max 2 attempts)
        assert mock_client.messages.create.call_count == 2


def test_generate_script_cost_calculation():
    with patch("pipeline.script_gen.anthropic.Anthropic") as MockCls:
        mock_client = MockCls.return_value
        resp = _make_anthropic_response(json.dumps(VALID_SCRIPT))
        resp.usage.input_tokens = 1000
        resp.usage.output_tokens = 500
        mock_client.messages.create.return_value = resp

        result = generate_script(_mock_topic(), _mock_channel())
        # $3/1M input + $15/1M output
        expected = 1000 * 3 / 1_000_000 + 500 * 15 / 1_000_000
        assert abs(result["_cost_usd"] - expected) < 1e-9
