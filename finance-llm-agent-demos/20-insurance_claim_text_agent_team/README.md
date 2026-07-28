## 保险理赔文本 Agent 团队

纯文本保险理赔 intake 示例，不做实时语音。输入事故描述后，生成字段抽取、缺失材料、风险信号和理赔员交接包。

```bash
cd 20-insurance_claim_text_agent_team
pip install -r requirements.txt
streamlit run app.py
```

仓库根目录运行：

```bash
./scripts/run_20_agent.sh
```

> 本项目仅用于技术学习与原型验证，不构成保险建议或赔付承诺。
