"""Regression checks for historical ranges and the revised daily schedule."""
import re
import unittest

from build_site import PLAN, Renderer, expand_plan_rows, inline, note


class PlanTablesTest(unittest.TestCase):
    def test_revised_blank_program_header_has_a_readable_display_label(self):
        header = ['日期', '區塊', '核心費曼', '快速比較', '',
                  '併入／安排內容', '替換與減量', '學習分鐘', '模考分鐘（另計）']
        row = ['9/21', 'A 區 CNN', 'Conv2D', 'CNN', '', '', '', '60', '0']
        renderer = Renderer('plan', plan=True)
        renderer.headings = [(3, 'ai', 'AI')]
        renderer.table_index = 1
        rendered = renderer.table([header, row])
        self.assertIn('<th scope="col">程式題型</th>', rendered)
        self.assertIn('<td data-label="程式題型"></td>', rendered)
        self.assertEqual(header[4], '', 'The source header must remain unchanged')

    def test_revised_daily_cells_and_subject_date_keys_are_preserved(self):
        security_header = ['日期', '範圍', '核心費曼', '快速比較', '學習分鐘', '模考分鐘（另計）']
        ai_header = ['日期', '複習', '核心費曼', '快速', '程式題型',
                     '併入／安排內容', '替換與減量', '學習分鐘', '模考分鐘（另計）']
        security_row = ['10/6', '科二', '核心', '比較', '60', '0']
        ai_row = ['10/6', '依雷達', '114-2 Q32', '快速', '114-Q39',
                  '辨認 inverted dropout', '替換小題組；不加時', '60', '0']
        mock_row = ['11/1', '刷題', '連續 90 分；模考另計', '', '114-Q1–50',
                    '完整模考', '不另排學習', '0', '90']
        renderer = Renderer('plan', plan=True)
        renderer.headings = [(3, 'schedule', '逐日表')]
        rendered = renderer.table([security_header, security_row])
        rendered += renderer.table([ai_header, ai_row, mock_row])
        for header, row in [(security_header, security_row), (ai_header, ai_row), (ai_header, mock_row)]:
            expected = '\n'.join(f'<td data-label="{label}">{inline(cell)}</td>'
                                 for label, cell in zip(header, row))
            self.assertIn(expected, rendered)
        keys = re.findall(r'data-completion-key="([^"]+)"', rendered)
        self.assertEqual(keys, ['ipas:completed:security:2026-10-06',
                                'ipas:completed:ai:2026-10-06', 'ipas:completed:ai:2026-11-01'])

    def test_current_source_has_96_unique_completion_keys(self):
        rendered, _ = note(PLAN, 'plan')
        keys = re.findall(r'data-completion-key="([^"]+)"', rendered)
        self.assertEqual(len(keys), 96)
        self.assertEqual(len(set(keys)), 96)
        self.assertEqual(sum(':security:' in key for key in keys), 41)
        self.assertEqual(sum(':ai:' in key for key in keys), 55)

    def test_v4_range_preserves_every_cell_for_each_day(self):
        header = ['日期', '複習', '核心費曼（20 分）', '快速（10 分）', '程式題型']
        row = ['10/27–10/30', '總複習',
               '還沒過清零；計算題各 3 題：Conv2D／Dense 參數量、混淆矩陣手算 P/R/F1、Grid 組合數、二維矩陣形狀',
               '正式卷程式題型重做（每個題型至少換一個變化版，不只重做原題）；一句話：時間複雜度（114-2 Q33）、MapReduce（樣題 Q1）',
               '上表全部']
        actual = expand_plan_rows([header, row])
        self.assertEqual(actual, [header] + [[f'10/{day}', *row[1:]] for day in range(27, 31)])

    def test_third_learning_table_keeps_ai_completion_controls(self):
        renderer = Renderer('plan', plan=True)
        rendered = renderer.render([
            '### 資安', '| 日期 | 範圍 | 完整費曼（2） | 快速（≈4） |',
            '| 9/21 | 科一 | A | B |',
            '### AI 歷史', '| 日期 | 區塊 | 完整費曼（2） | 快速（≈4） |',
            '| 10/3–10/4 | B 區 評估② | 過擬合判讀；交叉驗證選型 | 資料洩漏；SHAP；跨語言部署 F1 |',
            '### AI v4', '| 日期 | 複習 | 核心費曼（20 分） | 快速（10 分） | 程式題型 |',
            '| 10/5 | 依雷達 | C | D | E |',
            '### 刷題期', '| 日期 | 科目 | 階段 | 內容 |',
            '| 10/31 | AI 科三 | 休息（資安考試日） | |',
        ])
        self.assertIn('data-completion-key="ipas:completed:ai:2026-10-05"', rendered)
        self.assertIn('data-date="2026-10-05" data-kind="lesson" data-schedule="ai"', rendered)
        self.assertIn('data-date="2026-10-31" data-kind="rest" data-schedule="drill-summary"', rendered)
        self.assertEqual(rendered.count('data-completion-key='), 4)
        self.assertEqual(renderer.lesson_count, 4)

    def test_historical_shortened_range_uses_existing_distribution(self):
        header = ['日期', '區塊', '完整費曼（2）', '快速（≈4）']
        row = ['10/3–10/4', 'B 區 評估②', '過擬合判讀；交叉驗證選型', '資料洩漏；SHAP；跨語言部署 F1']
        self.assertEqual(expand_plan_rows([header, row]), [header,
            ['10/3', 'B 區 評估②', '過擬合判讀', '資料洩漏；跨語言部署 F1'],
            ['10/4', 'B 區 評估②', '交叉驗證選型', 'SHAP']])


if __name__ == '__main__':
    unittest.main()
