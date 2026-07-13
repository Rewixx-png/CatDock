from aiogram.fsm.state import State, StatesGroup

class SessionGenState(StatesGroup):
    waiting_for_api_id = State()
    waiting_for_api_hash = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()
    waiting_for_comment = State()

class AddSessionState(StatesGroup):
    confirming = State()
