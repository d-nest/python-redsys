# -*- coding: utf-8 -*-

import re
import hashlib
import json
import base64
import hmac
import ast
from Crypto.Cipher import DES3
from abc import ABCMeta, abstractmethod
from . import currencies, languages, transactions
from .response import Response
from .request import Request


# Calculated parameters
SIGNATURE_VERSION = 'Ds_SignatureVersion'
MERCHANT_PARAMETERS = 'Ds_MerchantParameters'
SIGNATURE = 'Ds_Signature'
DEFAULT_SIGNATURE_VERSION = 'HMAC_SHA256_V1'


class Client(object):

    REAL_ENDPOINT = None
    TEST_ENDPOINT = None

    secret_key = None
    endpoint = None

    __metaclass__ = ABCMeta

    def __init__(self, secret_key, sandbox=False):
        self.secret_key = secret_key
        self.endpoint = self.TEST_ENDPOINT if sandbox else self.REAL_ENDPOINT

    def create_request(self):
        return Request()

    @abstractmethod
    def create_response(self, signature, parameters, signature_version=DEFAULT_SIGNATURE_VERSION):
        pass

    @abstractmethod
    def prepare_request(self, request):
        pass

    def encode_parameters(self, parameters):
        encoded_parameters = (json.dumps(parameters)).encode()
        return ''.join(unicode(base64.encodestring(encoded_parameters), 'utf-8').splitlines())

    def decode_parameters(self, parameters):
        decoded_parameters = base64.standard_b64decode(parameters)
        return ast.literal_eval(decoded_parameters)

    def encrypt_3DES(self, order):
        pycrypto = DES3.new(base64.standard_b64decode(self.secret_key), DES3.MODE_CBC, IV=b'\0\0\0\0\0\0\0\0')
        order_padded = order.ljust(16, b'\0')
        return pycrypto.encrypt(order_padded)

    def sign_hmac256(self, encrypted_order, merchant_parameters):
        signature = hmac.new(encrypted_order, merchant_parameters, hashlib.sha256).digest()
        return base64.b64encode(signature)

    def generate_signature(self, order, merchant_parameters):
        return self.sign_hmac256(self.encrypt_3DES(order), merchant_parameters)


class RedirectClient(Client):
    REAL_ENDPOINT = u'https://sis.redsys.es/sis/realizarPago'
    TEST_ENDPOINT = u'https://sis-t.redsys.es:25443/sis/realizarPago'

    def create_response(self, signature, merchant_parameters, signature_version=DEFAULT_SIGNATURE_VERSION):
        response = Response(self.decode_parameters(merchant_parameters))
        calculated_signature = self.generate_signature(response.order, merchant_parameters)
        alphanumeric_characters = re.compile('[^a-zA-Z0-9]')
        safe_signature = re.sub(alphanumeric_characters, '', signature)
        safe_calculated_signature = re.sub(alphanumeric_characters, '', calculated_signature)
        if safe_signature != safe_calculated_signature:
            raise ValueError("The provided signature is not valid.")
        return response

    def prepare_request(self, request):
        merchant_parameters = self.encode_parameters(request.prepare_parameters())
        signature = self.sign_hmac256(self.encrypt_3DES(request.order), merchant_parameters)
        return {
            SIGNATURE_VERSION: DEFAULT_SIGNATURE_VERSION,
            MERCHANT_PARAMETERS: merchant_parameters,
            SIGNATURE: signature,
        }


class DirectClient(Client):
    REAL_ENDPOINT = u'https://sis.redsys.es/sis/services/SerClsWSEntrada'
    TEST_ENDPOINT = u'https://sis-t.redsys.es:25443/sis/services/SerClsWSEntrada'
