"""產生 main.ipynb（示範用 notebook）。用法： python src/make_notebook.py"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell("# 現金流與資金缺口模擬器\n第 7 組｜Option B 第六題。依序執行全部儲存格即可重現結果。"),
    nbf.v4.new_code_cell("import sys\nsys.path.insert(0, 'src')\nimport pandas as pd\n%matplotlib inline\n"
                         "from run import run\nfrom cashflow import item_monthly"),
    nbf.v4.new_markdown_cell("## 1. 輸入資料"),
    nbf.v4.new_code_cell("items, progress, scenarios, ledgers, summary = run(show=True)\n"
                         "print(f\"{len(items)} 個估價項目；成本 {items['cost'].sum():,}；合約價 {items['contract_price'].sum():,}\")\n"
                         "items.head(10)"),
    nbf.v4.new_code_cell("pd.DataFrame([s.__dict__ for s in scenarios])"),
    nbf.v4.new_markdown_cell("## 2. 方案比較"),
    nbf.v4.new_code_cell("summary.round(0)"),
    nbf.v4.new_markdown_cell("## 3. 逐月帳表（方案 A）"),
    nbf.v4.new_code_cell("ledgers[scenarios[0].scenario].round(0)"),
]
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, ROOT / "main.ipynb")
print("寫入 main.ipynb")
