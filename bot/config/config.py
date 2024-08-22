from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str
   
    REF_ID: str = '339631649'
    FAKE_USERAGENT: bool = True
    SLEEP_TIME: list[int] = [1800, 3600]
    
    USE_PROXY_FROM_FILE: bool = False


settings = Settings()


