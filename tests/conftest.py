"""Pytest configuration and fixtures."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: integration tests against real WB API")
    config.addinivalue_line("markers", "supplier_oper_names: extract unique supplier_oper_name values")
