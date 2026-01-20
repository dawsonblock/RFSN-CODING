"""Unified configuration schema for the RFSN controller.

This module defines the central configuration dataclass that captures all
controller settings. All configuration is explicit and typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass
class SandboxConfig:
    """Configuration for the sandbox execution environment."""
    
    image: str = "python:3.11-slim"
    mounts: List[str] = field(default_factory=list)
    cpu_limit: float = 2.0
    mem_limit: str = "2g"
    network_access: bool = False  # Default: no network inside sandbox


@dataclass
class ControllerConfig:
    """Central configuration for the RFSN controller.
    
    All settings are explicit and typed. This dataclass is immutable after
    creation to prevent configuration drift during execution.
    """
    
    # Repository settings
    repo_url: str = ""
    repo_ref: Optional[str] = None
    
    # Execution mode
    feature_mode: Literal["analysis", "repair", "refactor", "feature"] = "repair"
    
    # Test configuration
    test_command: str = "pytest -q"
    
    # Limits
    max_steps: int = 12
    max_steps_without_progress: int = 10
    
    # Sandbox settings
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    
    # Learning and policy
    learning_db_path: Optional[str] = None
    policy_mode: Literal["off", "bandit"] = "off"
    
    # Planning
    planner_mode: Literal["off", "dag"] = "off"
    
    # Repo indexing
    repo_index_mode: Literal["off", "on"] = "off"
    
    # Determinism
    seed: int = 1337
    
    # Model selection
    model: str = "deepseek-chat"
    
    # Output paths
    output_dir: str = ".rfsn"
    events_file: str = "events.jsonl"
    plan_file: str = "plan.json"
    eval_file: str = "eval.json"
    
    # Feature flags
    collect_finetuning_data: bool = False
    parallel_patches: bool = False
    enable_llm_cache: bool = False
    no_eval: bool = False
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.seed < 0:
            raise ValueError("seed must be >= 0")
        if self.feature_mode not in ("analysis", "repair", "refactor", "feature"):
            raise ValueError(f"Invalid feature_mode: {self.feature_mode}")


def config_from_cli_args(args) -> ControllerConfig:
    """Create a ControllerConfig from parsed CLI arguments.
    
    Args:
        args: Namespace from argparse.
        
    Returns:
        Configured ControllerConfig instance.
    """
    sandbox = SandboxConfig(
        image=getattr(args, "sandbox_image", "python:3.11-slim"),
        network_access=getattr(args, "network_access", False),
    )
    
    return ControllerConfig(
        repo_url=getattr(args, "repo", ""),
        repo_ref=getattr(args, "ref", None),
        feature_mode=getattr(args, "feature_mode", "repair"),
        test_command=getattr(args, "test", "pytest -q"),
        max_steps=getattr(args, "steps", 12),
        max_steps_without_progress=getattr(args, "max_steps_without_progress", 10),
        sandbox=sandbox,
        learning_db_path=getattr(args, "learning_db", None),
        policy_mode=getattr(args, "policy_mode", "off"),
        planner_mode=getattr(args, "planner_mode", "off"),
        repo_index_mode="on" if getattr(args, "repo_index", False) else "off",
        seed=getattr(args, "seed", 1337),
        model=getattr(args, "model", "deepseek-chat"),
        collect_finetuning_data=getattr(args, "collect_finetuning_data", False),
        parallel_patches=getattr(args, "parallel_patches", False),
        enable_llm_cache=getattr(args, "enable_llm_cache", False),
        no_eval=getattr(args, "no_eval", False),
    )
