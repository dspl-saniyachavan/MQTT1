import pytest
import sys
import os

# Backend root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
# Desktop root — needed by test_config.py and test_database.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'dspl-precision-pulse-desktop'))

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('JWT_SECRET', 'test-secret-key-for-testing-only-32chars')
os.environ.setdefault('SECRET_KEY', 'test-flask-secret-key-for-testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('MQTT_USE_TLS', 'false')
os.environ.setdefault('SQLITE_DB_PATH', '/tmp/test_precision_pulse.db')


@pytest.fixture(scope='function')
def app():
    from app import create_app
    flask_app = create_app()
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })
    from app.models import db
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def app_context(app):
    with app.app_context():
        yield app


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / 'precision_pulse.db')
