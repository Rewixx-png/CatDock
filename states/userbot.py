from aiogram.fsm.state import State, StatesGroup

class UserBotCreateState(StatesGroup):
    hub_selection = State()
    choosing_server = State()
    choosing_tariff = State()
    choosing_image = State()
    choosing_server_manually = State()
    confirming_creation = State()

class UserBotManageState(StatesGroup):
    managing = State()
    waiting_for_logs = State()
    confirming_transfer = State()
    upgrading_cpu = State()
    upgrading_ram = State()

class DeleteContainerState(StatesGroup):
    confirming_first_step = State()
    confirming_second_step = State()

class ChangeImageState(StatesGroup):
    choosing_new_image = State()
    confirming_change = State()

class ChangeServerState(StatesGroup):
    choosing_new_server = State()
    confirming_change = State()

class ReinstallState(StatesGroup):
    confirming_reinstall = State()

class ChangeNameState(StatesGroup):
    waiting_for_name = State()

class InteractiveLoginState(StatesGroup):
    in_session = State()
