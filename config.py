import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-cambiar-en-produccion')
    
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Convertir postgres:// a postgresql:// (Neon a veces usa postgres://)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Forzar el uso de psycopg2 en lugar de psycopg3
        # Cambia postgresql:// por postgresql+psycopg2://
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # Desarrollo local (MySQL)
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:database@localhost/horarios_universidad'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False