def claude_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Sonnet 4.5 pricing: $3/1M input, $15/1M output."""
    return input_tokens * 3 / 1_000_000 + output_tokens * 15 / 1_000_000


def elevenlabs_cost_usd(char_count: int) -> float:
    """ElevenLabs Creator tier: ~$0.18 per 1 000 characters."""
    return char_count * 0.18 / 1_000
