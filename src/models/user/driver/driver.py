import datetime
import random
import uuid

from flask import request

from src.common.database import Database
from src.common.errors import DBErrors
from src.common.sms import SMS
from src.common.utilites import Utils
from .constants import *
from .errors import *


class Driver(object):

    @staticmethod
    def check_email_validation(email):
        Utils.email_Isvalid(email)
        driver_data = Driver.find_driver(query={'Email': email})
        return driver_data

    @staticmethod
    def check_password_validation(password, driver_data):
        Utils.password_isvalid(password, PASSWORD_MIN_LENGTH)
        if not Utils.passwords_matching(password, driver_data['Password']):
            raise InCorrectPasswordError("wrong password associated with user email")

    @staticmethod
    def check_phone_number_validation(phone_number):
        Utils.phone_number_Isvalid(phone_number=phone_number)
        driver_data = Driver.find_driver(query={'PhoneNumber': phone_number})
        return driver_data

    @staticmethod
    def forget_password():
        phone_number, = Driver.check_json_vaild('PhoneNumber')
        driver_data = Driver.check_phone_number_validation(phone_number=phone_number)
        code_number = random.randrange((10 ** (FORGET_PASSWORD_CODE_LENGTH - 1) + 1), 10 ** FORGET_PASSWORD_CODE_LENGTH,
                                       1)
        SMS.send_sms(driver_data['PhoneNumber'],
                     FORGET_PASSWORD_SMS_MESSAGE + str(code_number))
        restoration_code = dict()
        restoration_code['Password restoration code'] = code_number
        Driver.update_db({"PhoneNumber": phone_number}, restoration_code)
        token = Utils.create_token({"PhoneNumber": driver_data['PhoneNumber']}, life_time_minutes=CODE_NUMBER_DURATION)
        return token, driver_data['Name']

    @staticmethod
    def change_password():
        token, new_password = Driver.check_json_vaild('Token', 'NewPassword')
        Utils.password_isvalid(new_password, PASSWORD_MIN_LENGTH)
        decoded_token = Utils.decode_token(token)
        hashed_password = Utils.hash_password(new_password)
        Driver.update_db({'PhoneNumber': decoded_token['PhoneNumber']},
                         {"Password": hashed_password})

    @staticmethod
    def check_code_number_validation():
        restoration_code, token = Driver.check_json_vaild('Restoration code', "Token")
        decoded_token = Utils.decode_token(token)
        driver_data = Driver.find_driver(query={'PhoneNumber': decoded_token['PhoneNumber']},
                                         options={'Password restoration code': 1})
        if driver_data['Password restoration code'] != int(restoration_code):
            raise CodeNumberIsInValid("the code number is invalid!")

        token_data = {"PhoneNumber": decoded_token['PhoneNumber']}
        return Utils.create_token(token_data, life_time_minutes=CHANGING_PASSWORD_DURATION)

    @staticmethod
    def registration():
        name, phone_number, email, password, birthday, image = Driver.check_json_vaild('Name', "PhoneNumber", 'Email',
                                                                                       'Password', 'Birthday', 'Image')
        try:
            Driver.check_phone_number_validation(phone_number=phone_number)
        except DriverError:
            try:
                Driver.check_email_validation(email=email)
            except DriverNotExistError:
                Utils.password_isvalid(password, PASSWORD_MIN_LENGTH)
                hashed_password = Utils.hash_password(password)
                query = {"Name": name, "PhoneNumber": phone_number, "Email": email, 'Birthday': birthday,
                         "Password": hashed_password,
                         "_id": uuid.uuid4().hex}
                Database.save_to_db(collection=DB_COLLECTION_DRIVER, query=query)
                Driver.save_image({"Name": name, "PhoneNumber": phone_number}, image)
            else:
                raise DriverExistError("the driver email already exist!")
        else:
            raise DriverExistError("the driver phone number already exist!")

    @staticmethod
    def find_driver(query, options=None):
        try:
            return Database.find_one(collection=DB_COLLECTION_DRIVER, query=query, options=options)
        except DBErrors:
            raise DriverNotExistError("driver does not exist.")

    @staticmethod
    def login():
        phone_number, password, coordination = Driver.check_json_vaild('PhoneNumber', "Password", 'Coordination')
        driver_data = Driver.check_phone_number_validation(phone_number=phone_number)
        Driver.check_password_validation(password, driver_data)
        Driver.store_driver_shift(driver_data, coordination)
        wanted_keys = {'Name', 'PhoneNumber', 'Email'}
        token_data = {key: value for key, value in driver_data.items() if key in wanted_keys}
        token = Utils.create_token(token_data, life_time_hours=TOKEN_LIFETIME)
        image = Driver.get_image({"PhoneNumber": phone_number})
        return token, image

    @staticmethod
    def get_coordination(query, options):
        return Database.find_one(collection=DB_collection_current_driver_shift, query=query, options=options)

    @staticmethod
    def store_driver_shift(query, coordination):  # storing the driver in database as current driver shift
        query.pop('Password')
        d = datetime.datetime.now().strftime("%H:%M")  # adding the time when the driver start the shift
        query.update(
            {"Started at": d, 'Start location': coordination, "Date": datetime.datetime.utcnow().strftime("%Y/%m/%d"),
             'created_at': datetime.datetime.utcnow(), 'Current location': coordination})
        try:
            Database.save_to_db(collection=DB_collection_current_driver_shift, query=query)
        finally:
            pass

    @staticmethod
    def update_coordination():
        token, coordination = Driver.check_json_vaild("Token", "Coordination")
        decoded_token = Utils.decode_token(token=token)
        Database.update(DB_collection_current_driver_shift, {'Email': decoded_token['Email']},
                        {"Current location": coordination}, False)

    @staticmethod
    def logout():
        token, = Driver.check_json_vaild("Token")
        decoded_token = Utils.decode_token(token=token)
        current_shift = Database.find_one_and_delete(collection=DB_collection_current_driver_shift,
                                                     query={'Email': decoded_token['Email']})
        current_shift['Finished at'] = datetime.datetime.now().strftime('%H:%M')
        current_shift[
            '_id'] = uuid.uuid4().hex  # here i changed the id of the document for not happening contradiction of the documents (which same driver can exist many times in this collection)
        current_shift['End location'] = current_shift['Current location']
        current_shift.pop('Current location')
        Database.save_to_db(collection=DB_collection_previous_driver_shift, query=current_shift)

    @staticmethod
    def update_db(query, update, upsert=False):
        Database.update(DB_COLLECTION_DRIVER, query, update, upsert)

    @staticmethod
    def get_image(filter):
        return Database.find_image(collection=DB_COLLECION_IMAGES, filter=filter)

    @staticmethod
    def save_image(image_details, image):
        Database.save_image(collection=DB_COLLECION_IMAGES, image_details=image_details, image=image)

    @staticmethod
    def check_json_vaild(
            *args):
        try:
            content = request.get_json()
            return tuple([content[i] for i in args] if len(args) != 0 else content)
        except KeyError:
            raise JsonInValid('The Json file is not valid')
