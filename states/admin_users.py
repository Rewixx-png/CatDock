from aiogram.fsm.state import State, StatesGroup

class AdminUserState(StatesGroup):
    waiting_for_input = State()
    managing_user = State()
    changing_balance = State()
    changing_role = State()
    confirming_deletion = State()
