"""Regression checks for the historical/v4 split in the AI schedule."""
import unittest

from build_site import Renderer, expand_plan_rows


class PlanTablesTest(unittest.TestCase):
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
