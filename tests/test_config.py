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


def test_retry_uses_provider_delay_then_succeeds(monkeypatch):
    import litellm
    from dutybench.harness import llm as llm_mod

    calls, sleeps = [], []
    err = litellm.RateLimitError("Quota exceeded. Please retry in 12.5s.", llm_provider="gemini", model="m")

    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise err
        return "ok"

    monkeypatch.setattr(llm_mod.litellm, "completion", fake_completion)
    monkeypatch.setattr(llm_mod.time, "sleep", sleeps.append)
    assert llm_mod._call_with_retries(model="m") == "ok"
    assert sleeps == [13.5]  # provider's 12.5s + 1s margin


def test_retry_backs_off_without_hint():
    from dutybench.harness.llm import _retry_delay
    assert [_retry_delay(Exception("busy"), a) for a in (1, 2, 3, 7)] == [2, 4, 8, 60]
