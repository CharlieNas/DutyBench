import litellm
import pytest

from dutybench.config import MODELS
from dutybench.harness.llm import Usage, cost_usd


@pytest.mark.parametrize("name", MODELS)
def test_our_prices_match_litellm(name):
    """Our price table is the one we cite; fail loudly if LiteLLM's map says otherwise."""
    lookup = MODELS[name].litellm_id.replace("openai/responses/", "")
    theirs = litellm.model_cost[lookup]
    ours = MODELS[name].price
    assert theirs["input_cost_per_token"] * 1e6 == pytest.approx(ours.input)
    assert theirs["output_cost_per_token"] * 1e6 == pytest.approx(ours.output)
    assert theirs["cache_read_input_token_cost"] * 1e6 == pytest.approx(ours.cached_input)


def test_cost_counts_cached_tokens_at_cached_price():
    price = MODELS["gpt-6.1-sol"].price
    # 1,000 input of which 800 cached, 100 output: 200*2 + 800*0.1 + 100*10 = 1,480 per 1M
    assert cost_usd(price, Usage(1000, 800, 100)) == pytest.approx(1480 / 1e6)
