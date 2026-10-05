"""Negative acceptance checks: run with python3 tests/test_verify_site.py."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import re
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_site as verify


class VerifyPlanTest(unittest.TestCase):
    def check_modified(self, before, after, check=verify.check2):
        original = verify.raw['index.html']
        self.assertIn(before, original)
        changed = original.replace(before, after, 1)
        with patch.dict(verify.raw, {'index.html': changed}), \
                patch.dict(verify.pages, {'index.html': verify.Page(changed)}):
            with self.assertRaises(AssertionError):
                check()

    def test_current_page_passes(self):
        with redirect_stdout(StringIO()):
            verify.check2()
            verify.check6()

    def test_new_column_content_cannot_be_dropped(self):
        self.check_modified(
            '<td data-label="併入／安排內容">用遮罩辨認 inverted dropout；說明保留值放大與訓練/推論差異</td>',
            '<td data-label="併入／安排內容"></td>')

    def test_program_header_cannot_be_blank(self):
        self.check_modified('<th scope="col">程式題型</th>', '<th scope="col"></th>')

    def test_mock_duration_cannot_change(self):
        self.check_modified('<td data-label="模考分鐘（另計）">90</td>',
                            '<td data-label="模考分鐘（另計）">60</td>')

    def test_mobile_label_cannot_be_blank(self):
        self.check_modified('data-label="程式題型"', 'data-label=""')

    def test_v6_calculation_days_cannot_revert_to_rest_or_lose_content(self):
        for day, topic in (('28', '混淆矩陣手算 P/R/F1 類 3 題'),
                           ('29', 'Grid 組合數類 3 題')):
            row = re.search(
                rf'<tr data-date="2026-10-{day}" data-kind="lesson" data-schedule="ai">.*?</tr>',
                verify.raw['index.html'], re.S)
            self.assertIsNotNone(row)
            before = row[0]
            for old, new in (('data-kind="lesson"', 'data-kind="rest"'),
                             (topic, '不排（資安計時重做日，AI 休息）'),
                             ('<td data-label="學習分鐘">20</td>',
                              '<td data-label="學習分鐘">0</td>')):
                with self.subTest(day=day, mutation=old):
                    self.assertIn(old, before)
                    self.check_modified(before, before.replace(old, new, 1))

    def test_lesson_progress_cannot_revert_to_64(self):
        self.check_modified('id="schedule-progress" max="66"',
                            'id="schedule-progress" max="64"')

    def test_completion_key_cannot_change(self):
        self.check_modified('data-completion-key="ipas:completed:ai:2026-10-06"',
                            'data-completion-key="ipas:completed:ai:2026-10-05"', verify.check6)


if __name__ == '__main__':
    unittest.main()
