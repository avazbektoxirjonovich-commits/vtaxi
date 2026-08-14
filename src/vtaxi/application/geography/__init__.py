"""Geography use cases: `GeographyService` (Step 8.2) -- administrative
areas and directions. GPS/nearby-search/real-time location are the Geo
Engine's job (docs/01-SOFTWARE-ARCHITECTURE.md SS14.8), not built yet.
"""

from vtaxi.application.geography.geography_service import GeographyService
from vtaxi.application.geography.ports import GeographyRepositoryProtocol, GeographyUnitOfWork

__all__ = ["GeographyRepositoryProtocol", "GeographyService", "GeographyUnitOfWork"]
