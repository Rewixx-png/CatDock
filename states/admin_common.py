from aiogram.fsm.state import State, StatesGroup

class AdminSupportState(StatesGroup):
    writing_answer = State()
    confirming_answer = State()

class AdminDeclineState(StatesGroup):
    waiting_for_reason = State()
