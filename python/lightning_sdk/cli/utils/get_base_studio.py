from typing import Optional

from lightning_sdk.base_studio import BaseStudio


def get_base_studio_id(studio_type: Optional[str]) -> Optional[str]:
    base_studios = BaseStudio()
    base_studios = base_studios.list()
    template_id = None

    if base_studios and len(base_studios):
        # if not specified by user, use the first existing template studio
        template_id = base_studios[0].id
        # else, try to match the provided studio_type to base studio name
        if studio_type:
            normalized_studio_type = studio_type.lower().replace(" ", "-")
            match = next(
                (s for s in base_studios if s.name.lower().replace(" ", "-") == normalized_studio_type),
                None,
            )
            if match:
                template_id = match.id

    return template_id
