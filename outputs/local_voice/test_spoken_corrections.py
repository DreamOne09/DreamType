import unittest
from dictation_guard import validate_edit
from spoken_corrections import comparison_source
from personalization import apply_explicit_layout


class SpokenRepairTests(unittest.TestCase):
    def test_adjacent_same_unit_repair_keeps_other_constraints(self):
        source='明天下午三點，不對，是四點半，在板橋車站見，不要去台北車站。'
        edited='明天下午四點半，在板橋車站見，不要去台北車站。'
        self.assertEqual(comparison_source(source),edited)
        validate_edit(source,edited)
        with self.assertRaises(ValueError):validate_edit(source,edited.replace('不要','要'))
        for wrong in ('五點半','四點','十四點半'):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):
                validate_edit(source,edited.replace('四點半',wrong))
        validate_edit(source,source)

    def test_quantity_repair_preserves_item_and_request(self):
        source='嗯那個我我想要兩杯無糖去冰拿鐵，啊不是，一杯就好。'
        validate_edit(source,'我想要一杯無糖去冰拿鐵。')
        with self.assertRaises(ValueError):validate_edit(source,'我想要三杯無糖去冰拿鐵。')
        with self.assertRaises(ValueError):validate_edit(source,'我想要一杯拿鐵。')
        source='請給我2盒口罩，啊不是，3盒就好。'
        validate_edit(source,'請給我3盒口罩。')
        with self.assertRaises(ValueError):validate_edit(source,'3盒口罩。')

    def test_same_place_repair_does_not_change_later_appointment(self):
        source='早上九點到南港，啊不對，改成十點半到南港，地點還是一樣。下午三點的會議沒有改，不要延後。'
        edited='早上十點半到南港，地點還是一樣。下午三點的會議沒有改，不要延後。'
        self.assertEqual(comparison_source(source),edited)
        validate_edit(source,edited)
        with self.assertRaises(ValueError):validate_edit(source,edited.replace('沒有改','改了'))

    def test_unsupported_repairs_stay_literal(self):
        for source in ('他說「三點，不對，四點」。','例如三點，不對，四點。',
                       '三點，不對，四天。','三點不是四點。','報價3元，不是4元。',
                       '負三元，不對，四元。','1.5元，不對，2元。',
                       '1,500元，不對，600元。','三點，不對，四點三十分。',
                       '九點到南港，啊不對，改成十點到板橋。',
                       '九點到南港，啊不對，改成十點到南港站。',
                       '想要兩杯咖啡不要加糖，啊不是，一杯就好。',
                       '報價一萬五，不是十五萬，含稅但不含運費。'):
            with self.subTest(source=source):self.assertEqual(comparison_source(source),source)
        with self.assertRaises(ValueError):validate_edit('報價3元，不是4元。','報價4元。')

    def test_layout_changes_only_whitespace_when_explicit(self):
        text='明天去板橋。  \n如果下雨就延期。'
        self.assertEqual(apply_explicit_layout(text,'不要條列，請寫成一個完整段落。'),
                         '明天去板橋。 如果下雨就延期。')
        for preference in ('','請用條列','不要寫成一個段落','不要用一個段落','如果很短就用一個段落',
                           '先寫成一個段落，再換行列出清單'):
            self.assertEqual(apply_explicit_layout(text,preference),text)


if __name__=='__main__':unittest.main()
