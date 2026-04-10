import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/precision_pulse')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET = os.environ['JWT_SECRET'] if 'JWT_SECRET' in os.environ else os.getenv('JWT_SECRET', '')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION = int(os.getenv('JWT_EXPIRATION', '86400'))

    # Flask session
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'pp_session:'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV', 'development') == 'production'

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # MQTT Configuration
    MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
    MQTT_PORT = int(os.getenv('MQTT_PORT', '18883'))
    MQTT_USE_TLS = os.getenv('MQTT_USE_TLS', 'true').lower() == 'true'
    MQTT_CA_CERTS = os.getenv('MQTT_CA_CERTS', 'config/ca.crt')
    MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))
