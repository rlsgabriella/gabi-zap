"""
safe_whatsapp_sender.py
Versão ajustada:
- Intervalo entre mensagens: 2 a 8 minutos
- Envio em blocos de 15 contatos com pausa de 30 minutos entre blocos
- Melhorias em caminhos, compatibilidade e clareza
"""

import os
import time
import json
import random
import logging
import tempfile
import platform
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from message_generator import generate_dynamic_message


# -----------------------
# Configurações padrão
# -----------------------
DEFAULT_CONFIG = {
    "contacts_file": "contatos.xlsx",
    "sent_log_file": "enviados.xlsx",
    "checkpoint_file": "checkpoint.json",
    "profile_dir": os.path.join(tempfile.gettempdir(), "whatsapp_session"),
    "min_interval_seconds": 120,          # 2 minutos
    "max_interval_seconds": 480,          # 8 minutos
    "block_size": 15,                     # Enviar 15 mensagens por bloco
    "block_pause_seconds": 1800,          # 30 minutos entre blocos
    "typing_delay_min": 0.03,
    "typing_delay_max": 0.12,
    "pause_probability": 0.07,
    "correction_probability": 0.05,
    "send_windows": [["08:00", "19:00"]],
    "max_messages_per_hour": 60,
    "max_messages_per_day": 300,
    "retry_attempts": 3,
    "retry_backoff_seconds": 5,
    "randomize_order": True,
    "perform_periodic_actions": True,
    "periodic_action_probability": 0.4,
    "webdriver_wait_seconds": 40
}


def load_config(path: str = "config.json") -> dict:
    """Carrega config.json e faz merge com defaults."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            conf = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(conf)
        # Garante caminhos relativos corretos
        base = os.path.dirname(os.path.abspath(__file__))
        for key in ["contacts_file", "sent_log_file", "checkpoint_file"]:
            merged[key] = os.path.join(base, merged[key])
        return merged
    return DEFAULT_CONFIG.copy()


def setup_logging(logfile="sender.log"):
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt,
                        handlers=[logging.FileHandler(logfile, encoding="utf-8"),
                                  logging.StreamHandler()])
    logging.info("Logger inicializado.")


def normalize_phone(raw: str) -> Optional[str]:
    if pd.isna(raw):
        return None
    s = "".join(ch for ch in str(raw) if ch.isdigit())
    return s if len(s) >= 10 else None


def within_send_windows(cfg: dict) -> bool:
    """Checa se o horário atual está dentro de alguma janela configurada."""
    now = datetime.now().time()
    for start_s, end_s in cfg["send_windows"]:
        start = datetime.strptime(start_s, "%H:%M").time()
        end = datetime.strptime(end_s, "%H:%M").time()
        if start <= end:
            if start <= now <= end:
                return True
        else:  # Janela cruza meia-noite
            if now >= start or now <= end:
                return True
    return False


def human_sleep(min_s: float, max_s: float):
    """Pausa humanizada entre mensagens."""
    total = random.uniform(min_s, max_s)
    logging.info(f"Aguardando {total/60:.1f} minutos antes do próximo envio...")
    time.sleep(total)


def send_whatsapp_message(driver, phone_number: str, message: str, cfg: dict) -> bool:
    """Envia uma mensagem via WhatsApp Web."""
    wait_seconds = cfg.get("webdriver_wait_seconds", 40)
    try:
        logging.info(f"Enviando para {phone_number}...")
        driver.get(f"https://web.whatsapp.com/send?phone={phone_number}")

        wait = WebDriverWait(driver, wait_seconds)
        message_box_xpath = "//footer//div[@role='textbox']"
        message_box = wait.until(EC.presence_of_element_located((By.XPATH, message_box_xpath)))

        time.sleep(random.uniform(1.5, 3.0))
        pyperclip.copy(message)

        modifier = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        message_box.send_keys(modifier, 'v')

        time.sleep(random.uniform(0.5, 1.0))
        message_box.send_keys(Keys.ENTER)
        time.sleep(random.uniform(2.0, 4.0))

        logging.info(f"Mensagem enviada com sucesso para {phone_number}")
        return True
    except Exception as e:
        logging.warning(f"Erro ao enviar para {phone_number}: {e}")
        return False


def save_checkpoint(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class SafeSender:
    def __init__(self, driver, cfg: dict):
        self.driver = driver
        self.cfg = cfg
        self.sent_log_file = cfg["sent_log_file"]
        self.checkpoint_file = cfg["checkpoint_file"]
        self.checkpoint = load_checkpoint(self.checkpoint_file)
        self.hourly_count = 0
        self.daily_count = 0

    def load_contacts(self) -> pd.DataFrame:
        df = pd.read_excel(self.cfg["contacts_file"])
        df = df.dropna(subset=['CONTATO'])
        df['CONTATO'] = df['CONTATO'].apply(normalize_phone)
        df = df.dropna(subset=['CONTATO'])

        if os.path.exists(self.sent_log_file):
            df_sent = pd.read_excel(self.sent_log_file)
            sent_set = set(df_sent['CONTATO'].astype(str))
            df = df[~df['CONTATO'].astype(str).isin(sent_set)].copy()

        if self.cfg.get("randomize_order", True):
            df = df.sample(frac=1).reset_index(drop=True)

        return df

    def persist_sent(self, sent_records: List[Dict[str, str]]):
        if not sent_records:
            return
        df_new = pd.DataFrame(sent_records)
        if os.path.exists(self.sent_log_file):
            df_old = pd.read_excel(self.sent_log_file)
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=['CONTATO'])
        else:
            df_combined = df_new
        df_combined.to_excel(self.sent_log_file, index=False)
        logging.info(f"Registro de enviados atualizado ({len(sent_records)} contatos).")

    def run(self):
        df = self.load_contacts()
        logging.info(f"Total de contatos a enviar: {len(df)}")

        last_index = self.checkpoint.get("last_index", -1)
        sent_records = []
        block_size = self.cfg.get("block_size", 15)
        block_pause = self.cfg.get("block_pause_seconds", 1800)

        for idx, row in df.reset_index(drop=True).iterrows():
            if idx <= last_index:
                continue

            contato = str(row['CONTATO'])
            nome = row.get('NOME', '').strip()
            mensagem = generate_dynamic_message(nome)

            if not within_send_windows(self.cfg):
                logging.info("Fora do horário permitido. Aguardando janela...")
                while not within_send_windows(self.cfg):
                    time.sleep(60)

            success = send_whatsapp_message(self.driver, contato, mensagem, self.cfg)

            if success:
                sent_records.append({
                    "NOME": nome,
                    "CONTATO": contato,
                    "TIMESTAMP": datetime.now().isoformat()
                })

            save_checkpoint(self.checkpoint_file, {"last_index": idx})

            # Pausa entre mensagens (2 a 8 min)
            if idx < len(df) - 1:
                human_sleep(self.cfg["min_interval_seconds"], self.cfg["max_interval_seconds"])

            # Pausa de bloco (a cada 15 contatos)
            if (idx + 1) % block_size == 0:
                logging.info(f"Bloco de {block_size} concluído. Aguardando 30 minutos antes de continuar...")
                time.sleep(block_pause)

        if sent_records:
            self.persist_sent(sent_records)
        logging.info("Envios finalizados com sucesso.")


def create_webdriver(profile_dir: str) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def main():
    cfg = load_config("config.json")
    setup_logging(cfg.get("log_file", "sender.log"))
    driver = create_webdriver(cfg["profile_dir"])

    try:
        driver.get("https://web.whatsapp.com")
        wait = WebDriverWait(driver, 90)
        logging.info("Aguardando login no WhatsApp Web...")
        wait.until(EC.presence_of_element_located((By.ID, "side")))
        logging.info("Login detectado. Iniciando envios...")
        sender = SafeSender(driver, cfg)
        sender.run()
    except Exception as e:
        logging.exception(f"Erro crítico: {e}")
    finally:
        time.sleep(5)
        driver.quit()
        logging.info("Execução encerrada.")


if __name__ == "__main__":
    main()
