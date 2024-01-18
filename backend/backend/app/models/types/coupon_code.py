import random
import string


class CouponCode(str):

    def __new__(cls, value=None, *args, **kwargs):
        if value is None:
            value = cls._generate_code()
        return super().__new__(cls, value)

    @classmethod
    def _generate_code(cls):
        # Generate a random string of alphanumeric characters
        random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=24))

        # Calculate checksum using a simple algorithm (e.g., sum of ASCII values)
        checksum = sum(map(ord, random_string)) % 10

        # Append checksum to the end of the random string
        coupon_code = random_string + str(checksum)
        return coupon_code

    @classmethod
    def validate(cls, value):
        # Validate the provided coupon code
        if not isinstance(value, str) or len(value) != 25 or sum(map(ord, value[:-1])) % 10 != int(value[-1]):
            raise ValueError("Invalid coupon code")
        return cls(value)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate
