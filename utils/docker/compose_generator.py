import yaml

def generate_compose_config(
    container_name: str,
    image_name: str,
    port: int,
    mem_limit: str,
    cpu_limit: str,
    restart_policy: str = "unless-stopped",
    command: list | str = None,
    working_dir: str = None
) -> str:
    """
    Генерирует содержимое docker-compose.yml.
    """
    
    formatted_mem = mem_limit
    if isinstance(mem_limit, int) or (isinstance(mem_limit, str) and mem_limit.isdigit()):
        formatted_mem = f"{mem_limit}M"
    elif isinstance(mem_limit, str) and mem_limit.lower().endswith('m'):
         formatted_mem = mem_limit.upper()

    service_config = {
        "container_name": container_name,
        "image": image_name,
        "hostname": "CatDock",
        "restart": restart_policy,
        "init": True,
        "ports": [
            f"{port}:8080"
        ],
        "volumes": [
            
            "./data:/user_data"
        ],
        "logging": {
            "driver": "json-file",
            "options": {
                "max-size": "10m",
                "max-file": "3"
            }
        },
        "deploy": {
            "resources": {
                "limits": {
                    "cpus": str(cpu_limit),
                    "memory": formatted_mem
                }
            }
        }
    }

    if command:
        service_config["command"] = command
    
    if working_dir:
        service_config["working_dir"] = working_dir

    config = {
        "services": {
            "app": service_config
        }
    }
    
    return yaml.dump(config, default_flow_style=False, sort_keys=False)
