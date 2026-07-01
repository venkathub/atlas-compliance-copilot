"""MLflow logging + HF-Hub adapter registration (ADR-0072) — GPU-free, behind mockable seams.

The training run logs params/metrics to MLflow, then — **before GPU teardown** — pushes the
fine-tuned adapter to the Hugging Face Hub (the durable artifact store) and registers an MLflow
model version whose **source URI is the HF repo+revision**. So the adapter is a versioned artifact
*decoupled from the disposable GPU*: pausing/destroying the GPU never loses the model.

Both heavy clients are injectable protocols (`HubClient`, `RegistryClient`) with lazy real impls
(`huggingface_hub` / `mlflow`, in the optional `train` group). Unit tests inject fakes, so this
module — and CI — never import them, touch the network, or need a GPU.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from atlas_training.config import RunConfig

HF_SCHEME = "hf"


class TrackingError(RuntimeError):
    """Raised on misconfiguration (missing repo/token) or an invalid registration source."""


@dataclass(frozen=True)
class ModelVersion:
    name: str
    version: str
    source: str  # the HF repo+revision URI — NEVER a GPU-local path
    run_id: str


def hf_source_uri(repo: str, revision: str) -> str:
    """The registry source URI for an adapter on the HF Hub: ``hf://<repo>@<revision>``."""
    if not repo or not revision:
        raise TrackingError(f"cannot build HF source URI from repo={repo!r} revision={revision!r}")
    return f"{HF_SCHEME}://{repo}@{revision}"


def is_hf_source(uri: str) -> bool:
    return uri.startswith(f"{HF_SCHEME}://") and "@" in uri.split("://", 1)[1]


# ── injectable seams ──────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class HubClient(Protocol):
    """Pushes a local adapter folder to the HF Hub and returns the created commit revision."""

    def push(self, adapter_path: str, repo: str, *, private: bool, token: str) -> str: ...


@runtime_checkable
class RegistryClient(Protocol):
    """Minimal MLflow surface the tracker needs (params/metrics + versions + aliases)."""

    def set_experiment(self, name: str) -> None: ...
    def start_run(self, run_name: str) -> str: ...  # returns run_id
    def log_params(self, params: dict) -> None: ...
    def log_metrics(self, metrics: dict, step: int | None = None) -> None: ...
    def end_run(self) -> None: ...
    # returns the created version string
    def create_model_version(self, name: str, source: str, run_id: str) -> str: ...
    # registry aliases (P7 promote/rollback, ADR-0079)
    def set_alias(self, name: str, alias: str, version: str) -> None: ...
    def get_version_by_alias(self, name: str, alias: str) -> str | None: ...


def run_params(config: RunConfig, prompt_template_sha: str | None = None) -> dict:
    """Flatten the pinned run config into MLflow params (the reproducibility record)."""
    p = {
        "base_model": config.base_model,
        "seed": config.seed,
        "quant.load_in_4bit": config.quant.load_in_4bit,
        "quant.bnb_4bit_quant_type": config.quant.bnb_4bit_quant_type,
        "quant.bnb_4bit_compute_dtype": config.quant.bnb_4bit_compute_dtype,
        "lora.r": config.lora.r,
        "lora.alpha": config.lora.alpha,
        "lora.dropout": config.lora.dropout,
        "train.epochs": config.train.epochs,
        "train.lr": config.train.lr,
        "train.batch_size": config.train.batch_size,
        "train.grad_accum": config.train.grad_accum,
        "train.max_seq_len": config.train.max_seq_len,
        "dataset.manifest": config.dataset.manifest,
        "dataset.train": config.dataset.train,
        "dataset.val": config.dataset.val,
    }
    if prompt_template_sha:
        p["dataset.prompt_template_sha"] = prompt_template_sha
    return p


@dataclass
class Tracker:
    """Orchestrates MLflow logging + HF push + registry version (source = HF repo+revision)."""

    registry: RegistryClient
    hub: HubClient
    hf_repo: str
    hf_token: str
    hf_private: bool = True

    @classmethod
    def from_env(cls, registry: RegistryClient, hub: HubClient) -> Tracker:
        repo = os.environ.get("ATLAS_HF_ADAPTER_REPO")
        token = os.environ.get("HF_TOKEN")
        if not repo:
            raise TrackingError("ATLAS_HF_ADAPTER_REPO is unset — configure the HF adapter repo")
        if not token:
            raise TrackingError("HF_TOKEN is unset — HF push requires a write token")
        private = os.environ.get("HF_PRIVATE", "true").lower() not in ("false", "0", "no")
        return cls(registry=registry, hub=hub, hf_repo=repo, hf_token=token, hf_private=private)

    def log_run(self, config: RunConfig, *, prompt_template_sha: str | None = None) -> str:
        """Set the experiment, start a run, log the pinned-config params. Returns the run_id."""
        self.registry.set_experiment(config.mlflow.experiment)
        run_id = self.registry.start_run(config.mlflow.run_name)
        self.registry.log_params(run_params(config, prompt_template_sha))
        return run_id

    def log_loss(self, step: int, *, train_loss: float, eval_loss: float | None = None) -> None:
        metrics = {"train_loss": train_loss}
        if eval_loss is not None:
            metrics["eval_loss"] = eval_loss
        self.registry.log_metrics(metrics, step=step)

    def log_metrics(self, metrics: dict) -> None:
        self.registry.log_metrics(metrics)

    def register_adapter(
        self, run_id: str, adapter_path: str | Path, register_as: str
    ) -> ModelVersion:
        """Push the adapter to HF (durable, pre-teardown), then register a version with HF source.

        Raises if the registration source is not an HF URI — guarding the DoD invariant that the
        registered artifact is decoupled from the disposable GPU (never a GPU-local path).
        """
        path = str(adapter_path)
        revision = self.hub.push(path, self.hf_repo, private=self.hf_private, token=self.hf_token)
        source = hf_source_uri(self.hf_repo, revision)
        if not is_hf_source(source):  # defensive: never register a local/GPU path
            raise TrackingError(f"refusing to register non-HF source: {source!r}")
        version = self.registry.create_model_version(register_as, source, run_id)
        self.registry.end_run()
        return ModelVersion(name=register_as, version=version, source=source, run_id=run_id)


# ── model-lifecycle: alias-based promote/rollback (P7 Task 6, ADR-0079) ─────────────────────────
#
# MLflow registry stages (Staging/Production/Archived) are deprecated (≥2.9, hard in 3.9/2026) in
# favour of **aliases + tags**. The production pointer is the ``@champion`` alias; the router
# resolves ``@champion`` (via ftTierModel), never a version number, so a rollback is instant. The
# last good champion is stashed under ``@previous_champion`` so ``rollback`` can re-point without
# external state. (A version freshly registered as a candidate would carry ``@challenger`` — the
# pre-promotion tag — which promote turns into the champion. Legacy-stage equivalent: promote ==
# transition to "Production" + archive the prior; narrated in docs/DECISIONS.md ADR-0079.)

CHAMPION = "champion"
PREVIOUS = "previous_champion"


@dataclass(frozen=True)
class PromotionOutcome:
    name: str
    champion: str            # the version @champion now points at
    previous: str | None     # the version @previous_champion now points at (rollback target)
    action: str              # "promote" | "rollback" | "noop"


def promote(registry: RegistryClient, name: str, version: str) -> PromotionOutcome:
    """Point ``@champion`` at ``version``; stash the outgoing champion under ``@previous_champion``.

    Idempotent: promoting the version that is already champion is a no-op that does NOT clobber the
    existing rollback target. GPU-free (registry metadata only).
    """
    version = str(version)
    current = registry.get_version_by_alias(name, CHAMPION)
    if current == version:
        return PromotionOutcome(name=name, champion=version, previous=None, action="noop")
    if current is not None:
        registry.set_alias(name, PREVIOUS, current)
    registry.set_alias(name, CHAMPION, version)
    return PromotionOutcome(name=name, champion=version, previous=current, action="promote")


def rollback(registry: RegistryClient, name: str) -> PromotionOutcome:
    """Re-point ``@champion`` back to ``@previous_champion`` (the last good version).

    The outgoing champion is swapped into ``@previous_champion`` so a rollback is itself reversible
    (re-promotable). Raises ``TrackingError`` if there is no prior version to roll back to.
    """
    prev = registry.get_version_by_alias(name, PREVIOUS)
    if prev is None:
        raise TrackingError(
            f"cannot roll back {name!r}: no @{PREVIOUS} alias — nothing was promoted over"
        )
    current = registry.get_version_by_alias(name, CHAMPION)
    registry.set_alias(name, CHAMPION, prev)
    if current is not None and current != prev:
        registry.set_alias(name, PREVIOUS, current)
    return PromotionOutcome(name=name, champion=prev, previous=current, action="rollback")


# ── real impls (lazy heavy imports; optional `train` group) ───────────────────────────────────────


class HfHubClient:
    """Real HF Hub push via `huggingface_hub.HfApi` (lazy import)."""

    def push(self, adapter_path: str, repo: str, *, private: bool, token: str) -> str:
        from huggingface_hub import HfApi  # lazy: optional `train` group

        api = HfApi(token=token)
        api.create_repo(repo_id=repo, private=private, exist_ok=True, repo_type="model")
        commit = api.upload_folder(
            repo_id=repo, folder_path=adapter_path, repo_type="model",
            commit_message="Atlas P6: upload QLoRA adapter",
        )
        # upload_folder returns a CommitInfo; prefer the resolved commit oid as the revision.
        return getattr(commit, "oid", None) or getattr(commit, "commit_id", None) or "main"


class MlflowRegistry:
    """Real MLflow tracking + registry via the `mlflow` client (lazy import).

    `MLFLOW_TRACKING_URI` selects the server (the infra/ mlflow container by default).
    """

    def __init__(self, tracking_uri: str | None = None):
        import mlflow  # lazy: optional `train` group

        self._mlflow = mlflow
        mlflow.set_tracking_uri(tracking_uri or os.environ.get("MLFLOW_TRACKING_URI"))
        self._active_run = None

    def set_experiment(self, name: str) -> None:
        self._mlflow.set_experiment(name)

    def start_run(self, run_name: str) -> str:
        self._active_run = self._mlflow.start_run(run_name=run_name)
        return self._active_run.info.run_id

    def log_params(self, params: dict) -> None:
        self._mlflow.log_params(params)

    def log_metrics(self, metrics: dict, step: int | None = None) -> None:
        self._mlflow.log_metrics(metrics, step=step)

    def end_run(self) -> None:
        self._mlflow.end_run()
        self._active_run = None

    def create_model_version(self, name: str, source: str, run_id: str) -> str:
        from mlflow.tracking import MlflowClient  # lazy

        client = MlflowClient()
        try:
            client.create_registered_model(name)
        except Exception:  # noqa: BLE001 - already-exists is the normal path
            pass
        mv = client.create_model_version(name=name, source=source, run_id=run_id)
        return mv.version

    def set_alias(self, name: str, alias: str, version: str) -> None:
        from mlflow.tracking import MlflowClient  # lazy

        MlflowClient().set_registered_model_alias(name, alias, str(version))

    def get_version_by_alias(self, name: str, alias: str) -> str | None:
        from mlflow.tracking import MlflowClient  # lazy

        try:
            return MlflowClient().get_model_version_by_alias(name, alias).version
        except Exception:  # noqa: BLE001 - alias-absent is the normal "no champion yet" path
            return None
