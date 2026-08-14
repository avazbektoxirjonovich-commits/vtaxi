"""Vehicle use cases: `VehicleService` (Step 8.3) -- vehicle management,
verification, vehicle/driver documents, and vehicle photos. A distinct
folder from `application/driver_verification/`: that folder's originally
planned responsibilities ("submit driver documents, approve/reject
driver, toggle availability_status") ended up split between
`application/identity/driver_service.py` (approve/reject/activate,
Step 8.1) and this module (driver *documents* specifically), once Vehicle
became its own bounded context (Step 5.3/7.5) -- `driver_verification/`
is not used by either and stays an empty placeholder.
"""

from vtaxi.application.vehicle.ports import VehicleRepositoryProtocol, VehicleUnitOfWork
from vtaxi.application.vehicle.vehicle_service import VehicleService

__all__ = ["VehicleRepositoryProtocol", "VehicleService", "VehicleUnitOfWork"]
