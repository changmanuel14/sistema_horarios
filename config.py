import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-cambiar-en-produccion')
    
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # 1. Neon a veces usa postgres://, lo estandarizamos a postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # 2. FORZAR el uso de psycopg2 (que es lo que tenemos en requirements.txt)
        # SQLAlchemy 2.x por defecto busca 'psycopg' (v3) si solo dice 'postgresql://'
        if database_url.startswith('postgresql://') and 'psycopg2' not in database_url:
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
            
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # Desarrollo local (MySQL)
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:database@localhost/horarios_universidad'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False