from lightning_sdk.cli.utils.get_base_studio import get_base_studio_id


def test_get_base_studio_id_no_templates(monkeypatch):
    """Test when no base studios are available."""
    from unittest.mock import MagicMock

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = []

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.utils.get_base_studio.BaseStudio", mock_base_studio_init)

    result = get_base_studio_id(None)
    assert result is None


def test_get_base_studio_id_default_first_template(monkeypatch):
    """Test that first template is used when studio_type is not specified."""
    from unittest.mock import MagicMock

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_template_2 = MagicMock()
    mock_template_2.id = "template-id-2"
    mock_template_2.name = "Data Science Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1, mock_template_2]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.utils.get_base_studio.BaseStudio", mock_base_studio_init)

    result = get_base_studio_id(None)
    assert result == "template-id-1"


def test_get_base_studio_id_matches_studio_type(monkeypatch):
    """Test that correct template is selected when studio_type matches."""
    from unittest.mock import MagicMock

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_template_2 = MagicMock()
    mock_template_2.id = "template-id-2"
    mock_template_2.name = "Data Science Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1, mock_template_2]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.utils.get_base_studio.BaseStudio", mock_base_studio_init)

    # Test with hyphenated name matching
    result = get_base_studio_id("data-science-template")
    assert result == "template-id-2"

    # Test case insensitivity
    result = get_base_studio_id("DATA-SCIENCE TEMPLATE")
    assert result == "template-id-2"


def test_get_base_studio_id_no_match_uses_first(monkeypatch):
    """Test that first template is used when studio_type doesn't match any."""
    from unittest.mock import MagicMock

    mock_template_1 = MagicMock()
    mock_template_1.id = "template-id-1"
    mock_template_1.name = "Python Template"

    mock_base_studio = MagicMock()
    mock_base_studio.list.return_value = [mock_template_1]

    def mock_base_studio_init(*args, **kwargs):
        return mock_base_studio

    monkeypatch.setattr("lightning_sdk.cli.utils.get_base_studio.BaseStudio", mock_base_studio_init)

    result = get_base_studio_id("nonexistent-template")
    assert result == "template-id-1"
