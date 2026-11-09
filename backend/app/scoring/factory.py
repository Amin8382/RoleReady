import os
from .interface import BaseScorer
from .mock_scorer import MockScorer
from .prometheus import PrometheusScorer

_scorer_instance: BaseScorer = None


def get_scorer() -> BaseScorer:
    """
    Factory function returning the active scorer based on the SCORER_BACKEND env var.
    Supported: 'mock' (default), 'ollama', 'vllm', 'hf_api'.
    """
    global _scorer_instance
    if _scorer_instance is not None:
        return _scorer_instance

    backend = os.getenv("SCORER_BACKEND", "mock").lower()

    if backend in ["ollama", "prometheus", "vllm", "hf_api"]:
        endpoint = os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:11434/api/generate")
        model_name = os.getenv("PROMETHEUS_MODEL_NAME", "prometheus-eval:7b-v2")
        timeout = float(os.getenv("PROMETHEUS_TIMEOUT_SECONDS", "45"))
        api_key = os.getenv("PROMETHEUS_API_KEY")
        _scorer_instance = PrometheusScorer(
            endpoint=endpoint,
            model_name=model_name,
            timeout_seconds=timeout,
            api_key=api_key,
            fallback_on_error=True,
        )
    else:
        _scorer_instance = MockScorer()

    return _scorer_instance

