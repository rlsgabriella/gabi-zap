# 📱 Gabi-Zap — Automação de Envio de Mensagens no WhatsApp

Automação para envio de mensagens personalizadas no WhatsApp utilizando **Python**, **API do WAHA**, e planilhas Excel.  
O sistema envia mensagens em intervalos controlados, registra contatos já processados e respeita horários específicos de operação.

⚠️ **LGPD:** Nenhum dado pessoal é enviado ao GitHub. As planilhas contendo números de telefone são ignoradas via `.gitignore`.

---

## ✨ Funcionalidades

- 📥 Leitura automática de contatos a partir de planilhas `.xlsx`
- ✉️ Envio de mensagens personalizadas usando a **API WAHA**
- ⏱️ Intervalo aleatório entre cada envio (2–5 minutos)
- 📦 Envio em blocos de 10 contatos com pausa automática de 1 hora
- 🕗 Envio apenas entre **08:00 e 19:00**, de segunda a sexta-feira
- 📑 Registro dos contatos já enviados em `enviados.xlsx`
- 🧠 Suporte a templates personalizados de mensagem
- 📝 Log automático de execução (`sender.log`)

---

## 🗂️ Estrutura do Projeto
```
│
├── app.py 
├── message_generator.py 
├── config.json 
├── checkpoint.json 
├── contatos.xlsx # 
├── enviados.xlsx # 
├── requirements.txt 
├── sender.log 
└── .gitignore
```


---

## 🔧 Como Executar

### 1️⃣ Instalar dependências
```bash
pip install -r requirements.txt
```
## Como rodar 
```bash
python app.py
```
