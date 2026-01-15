"""Generate a demo plan from sample input."""

from __future__ import annotations

import json

from shpoet.common.types import CharacterInput, SceneInput, UserPlayInput
from shpoet.expander.expander import expand_play_input


def build_sample_input() -> UserPlayInput:
    """Construct a minimal sample input for the expander demo."""

    return UserPlayInput(
        title="The Glass Crown",
        overview="A court fractures as an ambitious heir courts fate and power.",
        characters=[
            CharacterInput(
                name="Valen",
                description="An heir torn between duty and desire.",
                voice_traits=["measured", "resolute"],
            ),
            CharacterInput(
                name="Seren",
                description="A confidant who warns of peril and pride.",
                voice_traits=["candid", "warning"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A shadowed hall in the royal keep.",
                summary="Valen confides fears while Seren urges patience.",
                participants=["Valen", "Seren"],
            ),
            SceneInput(
                act=1,
                scene=2,
                setting="Antechamber before the throne.",
                summary="The court whispers of succession and unrest.",
                participants=["Valen"],
            ),
            SceneInput(
                act=2,
                scene=1,
                setting="A moonlit terrace overlooking the city.",
                summary="Valen vows to seize destiny despite warnings.",
                participants=["Valen", "Seren"],
            ),
        ],
    )


def main() -> None:
    """Run the expander demo and print outputs to stdout."""

    user_input = build_sample_input()
    brief, plan = expand_play_input(user_input)

    print(brief.markdown)
    print("\n---\n")
    print(json.dumps(plan.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()
