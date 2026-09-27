from __future__ import annotations

from dataclasses import dataclass

from models.product_state import CandidateProductState, WorkPilotMode


@dataclass(frozen=True)
class ProductModePolicy:
    mode: WorkPilotMode
    can_search: bool
    can_mutate: bool
    show_sources: bool
    show_profile: bool
    show_improvements: bool
    can_return_to_search: bool


def product_mode_policy(
    state: CandidateProductState,
) -> ProductModePolicy:
    mode = WorkPilotMode(state.mode)

    if mode is WorkPilotMode.SEARCH:
        return ProductModePolicy(
            mode=mode,
            can_search=True,
            can_mutate=True,
            show_sources=True,
            show_profile=True,
            show_improvements=True,
            can_return_to_search=False,
        )

    if mode is WorkPilotMode.CAREER:
        return ProductModePolicy(
            mode=mode,
            can_search=False,
            can_mutate=True,
            show_sources=True,
            show_profile=True,
            show_improvements=True,
            can_return_to_search=True,
        )

    return ProductModePolicy(
        mode=mode,
        can_search=False,
        can_mutate=False,
        show_sources=False,
        show_profile=False,
        show_improvements=True,
        can_return_to_search=False,
    )
