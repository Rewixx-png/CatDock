"""Public database API used by handlers, workers and the terminal service.

Keep imports in this module explicit by subsystem.  CatDock historically used
``import database as db`` everywhere, so a missing re-export only fails when a
button is pressed and is especially hard to diagnose.
"""

from .core import init_db, get_db, get_db_size
from .user import *
from .container_queries import *
from .admin_queries import *
from .settings_queries import *
from .payment_queries import *
from .user.api_tokens import *
from .user.login_codes import *
from .user.settings import *
from .transfer_queries import *
from .support_queries import *
from .auth_tokens import *
from .server_queries import *
from .log_queries import *
from .notification_queries import *
from .metric_queries import *

# Removed RewHost subsystems still have a few legacy callers.  Import their
# stable no-op API last so it deliberately wins over stale on-disk modules.
from .compat import *
