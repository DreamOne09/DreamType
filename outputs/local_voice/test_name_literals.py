import unittest
from personalization import protect_formatting_literals as protect, protect_identifiers, restore_identifiers

class NameLiteralTests(unittest.TestCase):
    def test_multiple_destinations_and_repeat_keep_every_occurrence(self):
        text='先到板橋車站拿文件，去桃園機場接人，再回板橋車站。'
        masked, values, prefix=protect(text)
        self.assertEqual(list(values.values()),['板橋車站','桃園機場','板橋車站'])
        self.assertEqual(restore_identifiers(masked, values, prefix),text)
        with self.assertRaises(ValueError):
            restore_identifiers(masked.replace(prefix+'2END','板橋車及'),values,prefix)

    def test_personal_spelling_and_identifier_overlap(self):
        text='請用ChatGPT，不用GPT4，去仁安醫院。寄給GPT@example.com。'
        masked,values,prefix=protect(text,vocabulary='GPT、ChatGPT、仁安醫院')
        self.assertEqual(list(values.values()),['ChatGPT','仁安醫院','GPT@example.com'])
        self.assertIn('GPT4',masked)
        self.assertEqual(restore_identifiers(masked,values,prefix),text)

    def test_repairs_and_stutters_remain_editable(self):
        for text in ('去板橋車站，不對，去台北車站。',
                     '去板橋車站板橋車站拿文件。','到仁安醫院，改成台大醫院。'):
            self.assertEqual(protect(text)[1],{})
        self.assertEqual(list(protect('去板橋車站，不對，電話0912345678。')[1].values()),['0912345678'])

    def test_supported_time_repair_masks_only_retained_name(self):
        text='下午三點到板橋車站，不對，四點到板橋車站。記得帶文件。'
        masked, values, prefix=protect(text)
        self.assertEqual(list(values.values()),['板橋車站'])
        self.assertEqual(restore_identifiers(masked,values,prefix),'下午四點到板橋車站。記得帶文件。')

    def test_no_invented_places_or_cross_clause_capture(self):
        text='去找媽媽，然後回家。今天要到銀行，再去醫院。'
        self.assertEqual(protect(text)[1],{})
        self.assertEqual(list(protect('先回家再去桃園機場。')[1].values()),['桃園機場'])

    def test_place_switch_and_translation_path(self):
        text='到板橋車站，然後去臺北市。'
        self.assertEqual(protect(text,taiwan_places=False)[1],{})
        self.assertEqual(protect_identifiers(text)[1],{})
        self.assertEqual(list(protect(text,vocabulary='板橋車站',taiwan_places=False)[1].values()),['板橋車站'])

    def test_marker_collision_and_longest_term(self):
        text='DTKEEP，使用夢想型態專業版。'
        masked,values,prefix=protect(text,vocabulary='夢想型態、夢想型態專業版')
        self.assertEqual(prefix,'DTKEEPX')
        self.assertEqual(list(values.values()),['夢想型態專業版'])
        self.assertEqual(restore_identifiers(masked,values,prefix),text)

if __name__=='__main__':unittest.main()
