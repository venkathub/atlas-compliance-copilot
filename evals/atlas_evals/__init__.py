"""Atlas evaluation & observability harness (RAGAS/DeepEval).

P2: the CI-gated eval harness. Golden + adversarial datasets and their loaders live here
(`atlas_evals.datasets`); the RAGAS runner, adversarial scorer, and merge gate land in later
P2 tasks. The harness talks to rag-engine only over HTTP (`atlas_evals.client`).
"""

__version__ = "0.1.0"
