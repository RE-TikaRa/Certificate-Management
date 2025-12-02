# 证书管理程序

基于 PySide6 + qfluentwidgets 的荣誉证书管理桌面应用，支持录入、统计、附件管理、备份、导入导出等。

-## 功能
- 首页仪表盘：LOGO 欢迎页
- 综合仪表盘：关键指标、统计图表、最近录入
- 荣誉录入：高级校验、成员/标签批量选择、附件上传
- 成员/标签管理：增删、排序（基础）
- 附件回收站：恢复、彻底删除
- 系统设置：目录、备份频率、主题、日志策略

## 运行
`ash
pip install -r requirements.txt
python -m src.main
`
可使用 main.bat 直接启动。

## 目录结构
`
src/
  config.py
  app_context.py
  main.py
  data/
  services/
  ui/
`

## 模板
src/resources/templates/awards_template.csv、.xlsx 可作为导入模板。
