from flask import Flask

from src.common.database import Database
from src.models.user.driver.views import Driver_blueprint
from src.models.user.moovit.views import moovit_blueprint
from src.models.user.passenger.views import passenger_blueprint

app = Flask(__name__)
app.config.from_object('src.config')
app.secret_key = app.config['SECRET_KEY']



@app.before_first_request
def ini_db():
    Database.init_Database()


@app.route('/')
def home():
    return 'ok'


app.register_blueprint(Driver_blueprint, url_prefix='/user/driver')
app.register_blueprint(passenger_blueprint, url_prefix='/user/passenger')
app.register_blueprint(moovit_blueprint, url_prefix='/user/moovit')
