from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    fhir_api_auth_server: str
    fhir_api_url: str
    fhir_api_client_id: str
    fhir_api_client_secret: str
    dw_connection: str
    saved_searches: str
    sql_query: str
    sql_query_not_have: str
    sender_email: str
    smtp_server: str
    smtp_port: int 
    app_password: str
    queue_data_path: str = "./queue_data"
    worker_count: int = 4
    failure_email: str
    demo: str


    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'  # specify encoding if necessary

settings = Settings()

