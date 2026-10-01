import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-cambiar-en-produccion')
    
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Normalizar el prefijo de la URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Asegurar que use el driver psycopg (v3) explícitamente
        if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:database@localhost/horarios_universidad'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False