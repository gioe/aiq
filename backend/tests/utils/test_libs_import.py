"""Test that shared libraries can be imported from the backend."""


def test_import_observability():
    """Verify that libs.observability can be imported from backend context."""
    from libs.observability import observability, ObservabilityFacade, SpanContext

    # Verify the singleton instance exists
    assert observability is not None

    # Verify it's an instance of the facade
    assert isinstance(observability, ObservabilityFacade)

    # Verify SpanContext is exported
    assert SpanContext is not None
