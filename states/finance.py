from aiogram.fsm.state import State, StatesGroup

class DepositState(StatesGroup):
    hub_selection = State()
    choosing_method = State()
    choosing_country = State()
    choosing_bank = State()
    confirming_deposit = State()

    waiting_for_amount = State()
    waiting_for_bank_name = State()
    waiting_for_card_payment = State()
    waiting_for_star_amount = State()
    waiting_for_crypto_amount = State()
    waiting_for_crypto_payment_confirmation = State()
    waiting_for_robokassa_amount = State()

class WithdrawalState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_details = State()

class ExtendSubscriptionState(StatesGroup):
    waiting_for_duration = State()
    confirming_extension = State()
