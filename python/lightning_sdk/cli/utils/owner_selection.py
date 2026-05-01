import os
from contextlib import suppress
from typing import Dict, List, Optional, TypedDict

import click
from simple_term_menu import TerminalMenu

from lightning_sdk.cli.legacy.exceptions import StudioCliError
from lightning_sdk.organization import Organization
from lightning_sdk.owner import Owner
from lightning_sdk.user import User
from lightning_sdk.utils.resolve import ApiException, _get_authed_user, _resolve_org, _resolve_user


class _OwnerMenuType(TypedDict):
    name: str
    is_org: bool


class OwnerMenu:
    """This class is used to select a teamspace owner (org/user) from a list of possible owners.

    It can be used to select an owner from a list of possible owners, or to resolve an owner from a name.
    """

    def _get_owner_from_interactive_menu(self, possible_owners: Dict[str, _OwnerMenuType]) -> _OwnerMenuType:
        owner_ids = sorted(possible_owners.keys())
        terminal_menu = self._prepare_terminal_menu_owners([possible_owners[k] for k in owner_ids])
        terminal_menu.show()

        selected_id = owner_ids[terminal_menu.chosen_menu_index]
        return possible_owners[selected_id]

    def _get_owner_from_name(self, owner: str, possible_owners: Dict[str, _OwnerMenuType]) -> _OwnerMenuType:
        for _, ts in possible_owners.items():
            if ts["name"]:
                return ts

        click.echo(f"Could not find Owner {owner}, please select it from the list:")
        return self._get_owner_from_interactive_menu(possible_owners)

    @staticmethod
    def _prepare_terminal_menu_owners(
        possible_owners: List[_OwnerMenuType], title: Optional[str] = None
    ) -> TerminalMenu:
        if title is None:
            title = "Please select a Teamspace-Owner out of the following:"

        return TerminalMenu(
            [f"{to['name']} ({'Organization' if to['is_org'] else 'User'})" for to in possible_owners],
            title=title,
            clear_menu_on_exit=True,
        )

    @staticmethod
    def _get_possible_owners(user: User) -> Dict[str, _OwnerMenuType]:
        user_api = user._user_api

        orgs = user_api._get_organizations_for_authed_user()
        owners: Dict[str, _OwnerMenuType] = {user.id: {"name": user.name, "is_org": False}}

        for org in orgs:
            owners[org.id] = {"name": org.name, "is_org": True}

        return owners

    def __call__(self, owner: Optional[str] = None) -> Owner:
        try:
            # try to resolve the teamspace from the name, environment or config
            resolved_owner = None
            with suppress(ApiException, ValueError, RuntimeError):
                resolved_owner = _resolve_org(owner)

            if resolved_owner is not None:
                return resolved_owner

            with suppress(ApiException, ValueError, RuntimeError):
                resolved_owner = _resolve_user(owner)

            if resolved_owner is not None:
                return resolved_owner

            if os.environ.get("LIGHTNING_NON_INTERACTIVE", "0") == "1":
                raise ValueError(
                    "Owner selection is not supported in non-interactive mode. Please provide an owner name."
                )

            # if the owner is not resolved, try to get the owner from the interactive menu
            # this could mean that either no owner was provided or the provided owner is not valid
            user = _get_authed_user()

            possible_owners = self._get_possible_owners(user)
            if owner is None:
                owner_dict = self._get_owner_from_interactive_menu(possible_owners=possible_owners)

            else:
                owner_dict = self._get_owner_from_name(owner=owner, possible_owners=possible_owners)

            if owner_dict.get("is_org", False):
                return Organization(owner_dict.get("name", None))

            return User(owner_dict.get("name", None))
        except KeyboardInterrupt:
            raise KeyboardInterrupt from None

        except Exception as e:
            raise StudioCliError(
                f"Could not find the given Teamspace-Owner {owner}. "
                "Please contact Lightning AI directly to resolve this issue."
            ) from e
