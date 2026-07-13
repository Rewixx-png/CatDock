from aiogram.fsm.state import State, StatesGroup

class TerminalState(StatesGroup):
    waiting_for_command = State()

class AdminOrphanState(StatesGroup):
    confirming_deletion = State()

class AdminCheckState(StatesGroup):
    confirming_orphan_deletion = State()

class AdminFixLoopState(StatesGroup):
    confirming_deletion = State()

class ImageUpdateState(StatesGroup):
    confirming_update = State()

class AdminUnfreezeAllState(StatesGroup):
    waiting_for_reason = State()

class AdminSessionScanState(StatesGroup):
    confirming_delete = State()

class ServerAddState(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_ip = State()
    waiting_for_password = State()

class ServerDeleteState(StatesGroup):
    choosing_server = State()
    confirming_deletion = State()

class ServerEditState(StatesGroup):
    choosing_server = State()
    viewing_details = State()
    waiting_for_new_value = State()

class ServerStatsState(StatesGroup):
    choosing_metric = State()
    choosing_server = State()
    choosing_period = State()
