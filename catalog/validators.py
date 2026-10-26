from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def ean13_is_valid(value):
    if len(value) != 13 or not value.isdigit():
        return False
    digits = [int(c) for c in value]
    # Weights 1,3,1,3,... over the first 12 digits; the 13th is the check digit
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def validate_ean13(value):
    if not ean13_is_valid(value):
        raise ValidationError(_('"%(value)s" is not a valid EAN-13 barcode.'), params={'value': value})
