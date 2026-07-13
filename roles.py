from enum import IntEnum

class UserRole(IntEnum):
    PARTICIPANT = 0
    JUNIOR_ADMIN = 1
    ADMIN = 2
    SENIOR_ADMIN = 3
    CO_OWNER = 4
    OWNER = 5

ROLE_NAMES = {
    UserRole.PARTICIPANT: "Участник",
    UserRole.JUNIOR_ADMIN: "Мл. Администратор",
    UserRole.ADMIN: "Администратор",
    UserRole.SENIOR_ADMIN: "Ст. Администратор",
    UserRole.CO_OWNER: "Со-Владелец",
    UserRole.OWNER: "Владелец"
}

DEFAULT_ROLE = UserRole.PARTICIPANT.name
