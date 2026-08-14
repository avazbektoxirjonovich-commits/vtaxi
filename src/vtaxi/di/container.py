"""Composition root placeholder.

This module will build the dependency-injection container (candidate:
`dishka`, see docs/01 ADR-005) that wires infrastructure adapters into
application use cases and injects them into Aiogram handlers via
middleware. Left empty until Step 8 (Services) and Step 9 (Repositories)
give it real ports and adapters to wire -- there is nothing to inject yet.
"""
