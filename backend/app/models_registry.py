"""Imports every model module so Base.metadata knows all tables.

Alembic autogenerate reads Base.metadata — a model that is not imported
here is invisible to migrations and will silently never get a table.
"""

from app.core.tenancy import models as tenancy_models  # noqa: F401
from app.core.auth import models as auth_models  # noqa: F401
from app.core.modules import models as module_models  # noqa: F401
from app.core.audit import models as audit_models  # noqa: F401
