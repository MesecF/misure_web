from django.test import SimpleTestCase

from .validators import ean13_is_valid


class Ean13Tests(SimpleTestCase):
    def test_valid_barcodes(self):
        for code in ['4006381333931', '5901234123457', '9780201379624']:
            self.assertTrue(ean13_is_valid(code), code)

    def test_invalid_barcodes(self):
        for code in ['4006381333932', '400638133393', '40063813339310', '40063813339A1', '']:
            self.assertFalse(ean13_is_valid(code), code)
