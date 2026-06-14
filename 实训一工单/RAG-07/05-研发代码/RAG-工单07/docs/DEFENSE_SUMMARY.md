# 答辩说明

## 一句话版

- [evaluation_questions.json](/C:/Users/刘禹含/Desktop/RAG-工单01/data/processed/evaluation_questions.json)
  这个文件是评测题库，存放了 10 个验收问题及其对应的标准答案，作为整套评估流程的输入。

- [EVALUATION_REPORT.md](/C:/Users/刘禹含/Desktop/RAG-工单01/docs/EVALUATION_REPORT.md)
  这个文件是人工验收报告，记录了 10 道题逐题核对后的正确性结论，以及 RAG 和纯 LLM 的效果对比。

- [EVALUATION.md](/C:/Users/刘禹含/Desktop/RAG-工单01/docs/EVALUATION.md)
  这个文件是评估方法说明，主要说明本项目采用了什么评估流程、用了哪些 RAGAS 指标、最后得到了什么结果。

- [ACCEPTANCE_CHECKLIST.md](/C:/Users/刘禹含/Desktop/RAG-工单01/docs/ACCEPTANCE_CHECKLIST.md)
  这个文件是验收清单，用来对应工单中的准确率、响应时间、稳定性和容错机制等要求，看系统当前完成到了什么程度。

- [ragas_eval_results.csv](/C:/Users/刘禹含/Desktop/RAG-工单01/data/exports/ragas_eval_results.csv)
  这个文件是逐题评估明细，按题目保存了问题、标准答案、RAG答案、纯LLM答案、耗时以及各项评估指标，适合表格化查看。

- [ragas_eval_summary.json](/C:/Users/刘禹含/Desktop/RAG-工单01/data/exports/ragas_eval_summary.json)
  这个文件是整体评估汇总，保存了总题数、RAGAS 总体指标、字段说明和每道题的完整记录。

## 汇报版

本项目围绕 `招股说明书1.pdf` 搭建了一套基于 PDF 的问答系统。为了验证系统效果，我先整理了 `evaluation_questions.json` 作为标准题库，然后通过 RAG 和纯 LLM 两条链路分别生成答案，并把逐题结果导出到 `ragas_eval_results.csv`，同时将整体指标汇总到 `ragas_eval_summary.json`。在此基础上，我又编写了 `EVALUATION.md` 说明评估方法，用 `EVALUATION_REPORT.md` 记录人工验收结果，并通过 `ACCEPTANCE_CHECKLIST.md` 对照工单验收要求进行整理，最终形成了一套既能量化评估、又能人工核验的完整交付材料。

## 极简口述版

如果老师只给很短时间，可以直接这样说：

“我把这个项目的评估材料分成了六部分：题库文件、评估方法文件、人工验收报告、验收清单、逐题结果表和总体结果汇总。这样既能展示系统每道题答得怎么样，也能展示整体指标和是否满足工单要求。” 
