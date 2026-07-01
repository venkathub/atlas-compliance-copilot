"""Atlas training subsystem (P6): QLoRA fine-tuning pipeline + experiment tracking.

GPU-free by default. Only `train.py` / `infer.py` import the heavy ML stack (the `train`
dependency-group), and only inside the episodic GPU window. Everything else — config loading,
dataset curation, manifest validation, scoring, report generation — runs offline in CI.
"""
