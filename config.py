import os
from dotenv import load_dotenv
# Importamos quote_plus para manejar caracteres especiales en la contraseña
from urllib.parse import quote_plus
# Importamos las credenciales desde nuestro archivo
from conexion import Conhost, Conuser, Conpassword, Condb

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-cambiar-en-produccion')
    
    # Detectar automáticamente si estamos en desarrollo local o producción
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Producción (Koyeb + Neon.tech)
        # Neon a veces usa postgres:// en lugar de postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # Desarrollo local (MySQL)
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{quote_plus(Conuser)}:{quote_plus(Conpassword)}@{Conhost}/{Condb}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False