from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class BaseResponse(BaseModel):
    status: str = Field(..., description="Статус запроса (success/error)")

class MessageResponse(BaseResponse):
    message: str

class GenerateTokenResponse(BaseResponse):
    login_token: str = Field(..., description="Токен для диплинка")
    bot_username: str = Field(..., description="Юзернейм бота")

class CheckTokenResponse(BaseResponse):
    api_key: Optional[str] = Field(None, description="API ключ (если авторизация успешна)")

class VersionResponse(BaseModel):
    version: str
    bot_username: str

class ServerStatusItem(BaseModel):
    id: str
    name: str
    status: str
    cpu: str
    ram: str
    disk: str
    uptime: str
    top_load: str
    ping: Union[int, str, None] = "N/A"
    net: bool = False

class ServerStatusMeta(BaseModel):
    last_updated: float
    update_interval: int

class ServerStatusResponse(BaseResponse):
    data: List[ServerStatusItem]
    meta: ServerStatusMeta

class ServiceHealth(BaseModel):
    status: str
    latency: float

class SystemHealthData(BaseModel):
    api: ServiceHealth
    database: ServiceHealth

class SystemHealthResponse(BaseResponse):
    data: SystemHealthData

class UserPhotoResponse(BaseResponse):
    data_url: Optional[str] = None
    message: Optional[str] = None

class VerifyResponse(BaseResponse):
    message: str
    bot_username: str

class LogsDataResponse(BaseResponse):
    data: str
    meta: Dict[str, str]

class UserBase(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: str
