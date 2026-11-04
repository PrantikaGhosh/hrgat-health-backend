import random

OTP_MIN = 1000
OTP_MAX = 9999
OTP_VALIDITY_MINUTES = 5


def generate_otp() -> int:
    return random.randint(OTP_MIN, OTP_MAX)
