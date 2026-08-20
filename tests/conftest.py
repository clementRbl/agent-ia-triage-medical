import pytest

from triage.data.anonymize import Anonymiseur


@pytest.fixture(scope="session")
def anonymiseur() -> Anonymiseur:
    """Instance partagee : le chargement des deux modeles spaCy est couteux."""
    return Anonymiseur()
