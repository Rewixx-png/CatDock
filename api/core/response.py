import math
import typing
from starlette.responses import JSONResponse

def _clean_data(data: typing.Any) -> typing.Any:
    """
    Рекурсивно заменяет float('nan') и float('inf') на None (или 0.0),
    чтобы json.dumps не падал с ошибкой.
    """
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None 
        return data
    
    if isinstance(data, dict):
        return {k: _clean_data(v) for k, v in data.items()}
    
    if isinstance(data, list):
        return [_clean_data(v) for v in data]
    
    if isinstance(data, tuple):
        return tuple(_clean_data(v) for v in data)
        
    return data

class SafeJSONResponse(JSONResponse):
    """
    Кастомный класс ответа, который автоматически "чистит" данные
    от NaN и Infinity перед сериализацией в JSON.
    Это предотвращает падение API с 500 ошибкой.
    """
    def render(self, content: typing.Any) -> bytes:
        try:
            
            return super().render(content)
        except ValueError as e:
            
            if "Out of range float" in str(e):
                cleaned_content = _clean_data(content)
                return super().render(cleaned_content)
            raise e
