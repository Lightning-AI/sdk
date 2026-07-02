from unittest.mock import MagicMock

from lightning_sdk.cli.utils.studio_selection import StudiosMenu


def test_get_possible_studios_filters_by_user_id(monkeypatch):
    """Test that _get_possible_studios only returns studios owned by the current user."""
    mock_user = MagicMock()
    mock_user.id = "user-123"

    mock_studio_1 = MagicMock()
    mock_studio_1.name = "my-studio"
    mock_studio_1._studio = MagicMock()
    mock_studio_1._studio.user_id = "user-123"

    mock_studio_2 = MagicMock()
    mock_studio_2.name = "other-studio"
    mock_studio_2._studio = MagicMock()
    mock_studio_2._studio.user_id = "user-456"

    mock_studio_3 = MagicMock()
    mock_studio_3.name = "another-studio"
    mock_studio_3._studio = MagicMock()
    mock_studio_3._studio.user_id = "user-123"

    mock_teamspace = MagicMock()
    mock_teamspace.studios = [mock_studio_1, mock_studio_2, mock_studio_3]

    monkeypatch.setattr("lightning_sdk.cli.utils.studio_selection._get_authed_user", lambda: mock_user)

    menu = StudiosMenu(teamspace=mock_teamspace)
    possible_studios = menu._get_possible_studios()

    assert len(possible_studios) == 2
    assert "my-studio" in possible_studios
    assert "another-studio" in possible_studios
    assert "other-studio" not in possible_studios


def test_get_possible_studios_returns_empty_when_no_matches(monkeypatch):
    """Test that _get_possible_studios returns empty dict when no studios match user id."""
    mock_user = MagicMock()
    mock_user.id = "user-123"

    mock_studio_1 = MagicMock()
    mock_studio_1.name = "other-studio-1"
    mock_studio_1._studio = MagicMock()
    mock_studio_1._studio.user_id = "user-456"

    mock_studio_2 = MagicMock()
    mock_studio_2.name = "other-studio-2"
    mock_studio_2._studio = MagicMock()
    mock_studio_2._studio.user_id = "user-789"

    mock_teamspace = MagicMock()
    mock_teamspace.studios = [mock_studio_1, mock_studio_2]

    monkeypatch.setattr("lightning_sdk.cli.utils.studio_selection._get_authed_user", lambda: mock_user)

    menu = StudiosMenu(teamspace=mock_teamspace)
    possible_studios = menu._get_possible_studios()

    assert len(possible_studios) == 0
