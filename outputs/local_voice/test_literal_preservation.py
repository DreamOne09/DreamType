"""Taiwan phone spellings must survive formatting byte-for-byte."""
import unittest
from personalization import protect_identifiers, restore_identifiers, validate_identifiers


class PhoneLiteralTests(unittest.TestCase):
    def test_phone_forms_are_fully_masked_and_restored(self):
        for phone in ('02-23456789','(02)2345-6789','03-1234567','0912 345 678',
                      '+886 912 345 678','+886-2-2345-6789','+886912345678',
                      '0912345678','0912-345-678'):
            with self.subTest(phone=phone):
                original='電話是'+phone+'，不要改成其他號碼。'
                masked,values,prefix=protect_identifiers(original)
                self.assertEqual(list(values.values()),[phone])
                self.assertNotIn(phone,masked)
                self.assertEqual(restore_identifiers(masked,values,prefix),original)
                with self.assertRaises(ValueError):
                    validate_identifiers(original,original.replace(phone,phone[:-1]+'0'))

    def test_two_contacts_keep_order_and_negation(self):
        original='請打 (02)2345-6789，不要打 +886 912 345 678。'
        masked,values,prefix=protect_identifiers(original)
        self.assertEqual(list(values.values()),['(02)2345-6789','+886 912 345 678'])
        self.assertEqual(restore_identifiers(masked,values,prefix),original)
        swapped=masked.replace(prefix+'0END','TEMP').replace(prefix+'1END',prefix+'0END').replace('TEMP',prefix+'1END')
        with self.assertRaises(ValueError):restore_identifiers(swapped,values,prefix)

    def test_ordinary_numbers_and_spoken_corrections_are_not_phones(self):
        for original in ('三點，不對四點半。','預算 1500 元，改成 1800 元。','下午 02:30 出發。','訂單 A0912345678B。'):
            masked,values,_=protect_identifiers(original)
            self.assertEqual(values,{})
            self.assertEqual(masked,original)


if __name__=='__main__':unittest.main()
