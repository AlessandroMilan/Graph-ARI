"""
mexari._forecasting
==================
Reusable helpers for chronology-aware spatiotemporal forecasting experiments.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class TemporalSplit:
    """Chronological split boundaries over the raw time axis."""

    train_end: int
    val_start: int
    val_end: int
    test_start: int
    test_end: int
    gap: int


def make_temporal_split(
    num_weeks: int,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    gap: int = 0,
) -> TemporalSplit:
    """Build a chronological train/val/test split with an optional gap between regions."""
    if num_weeks <= 0:
        raise ValueError("num_weeks must be positive.")
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be in (0, 1).")
    if not 0 <= val_ratio < 1:
        raise ValueError("val_ratio must be in [0, 1).")
    if train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio must be smaller than 1.")
    if gap < 0:
        raise ValueError("gap must be non-negative.")

    train_end = max(1, int(num_weeks * train_ratio))
    remaining_weeks = num_weeks - train_end
    val_weeks = max(1, int(num_weeks * val_ratio)) if val_ratio > 0 else 0
    val_weeks = min(val_weeks, max(0, remaining_weeks - 1))

    val_start = min(train_end + gap, num_weeks)
    val_end = min(val_start + val_weeks, num_weeks)
    test_start = min(val_end + gap, num_weeks)
    test_end = num_weeks

    if test_start >= test_end:
        raise ValueError(
            "The requested split leaves no weeks for the test region. "
            "Reduce the gap or adjust the split ratios."
        )
    if val_ratio > 0 and val_start >= val_end:
        raise ValueError(
            "The requested split leaves no weeks for the validation region. "
            "Reduce the gap or adjust the split ratios."
        )

    return TemporalSplit(
        train_end=train_end,
        val_start=val_start,
        val_end=val_end,
        test_start=test_start,
        test_end=test_end,
        gap=gap,
    )


def region_window_starts(
    region_start: int,
    region_end: int,
    window: int,
    horizon: int,
    stride: int = 1,
) -> list[int]:
    """Return window start indices whose history and target stay inside one region."""
    if stride <= 0:
        raise ValueError("stride must be positive.")
    usable_stop = region_end - window - horizon + 1
    if usable_stop <= region_start:
        return []
    return list(range(region_start, usable_stop, stride))


def train_scaler_from_region(
    time_signal: torch.Tensor,
    train_end: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Compute train-only per-node scaling statistics over the raw time axis."""
    if train_end <= 0:
        raise ValueError("train_end must be positive.")
    scale_mean = time_signal[:train_end].mean(dim=0, keepdim=True)
    scale_std = time_signal[:train_end].std(
        dim=0,
        keepdim=True,
        unbiased=False,
    ).clamp_min(1e-6)
    return scale_mean, scale_std


def scale_time_signal(
    time_signal: torch.Tensor,
    scale_mean: torch.Tensor,
    scale_std: torch.Tensor,
) -> torch.Tensor:
    """Apply precomputed per-node scaling statistics."""
    return (time_signal - scale_mean) / scale_std