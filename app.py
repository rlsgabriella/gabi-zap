"""
safe_whatsapp_sender.py
Versão refatorada com:
- modularização (leitura, validação, humanização, envio, checkpoint)
- delays variáveis, digitação simulada, correções/hesitações
- randomização de ordem / janelas de envio
- retry/backoff, checkpoint para retomar, pause seguro
- logging e validação
- configuração externalizada em config.json
"""

import os
import time
import json
import random
import string
import logging
import tempfile
from datetime import datetime, time as time_cls, timedelta
from typing import List, Dict, Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from message_generator import generate_dynamic_message
import pyperclip

# -----------------------
# Helpers / Config loader
# -----------------------
DEFAULT_CONFIG = {
    "contacts_file": "contatos.xlsx",
    "sent_log_file": "enviados.xlsx",
    "checkpoint_file": "checkpoint.json",
    "profile_dir": os.path.join(tempfile.gettempdir(), "whatsapp_session"),
    "min_interval_seconds": 30,
    "max_interval_seconds": 120,
    "typing_delay_min": 0.03,
    "typing_delay_max": 0.12,
    "pause_probability": 0.07,            # probabilidade de pausa/hesitação curta durante a digitação
    "correction_probability": 0.05,       # probabilidade de simular correção (backspace)
    "send_windows": [                      # janelas de envio (horário local) -> [(start, end), ...]
        ["09:00", "12:00"],
        ["14:00", "18:00"]
    ],
    "max_messages_per_hour": 60,
    "max_messages_per_day": 300,
    "retry_attempts": 3,
    "retry_backoff_seconds": 5,
    "randomize_order": False,
    "perform_periodic_actions": True,
    "periodic_action_probability": 0.4,    # durante waits, probabilidade de executar ação
    "webdriver_wait_seconds": 40
}


def load_config(path: str = "config.json") -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            conf = json.load(f)
        # merge defaults for missing keys
        merged = DEFAULT_CONFIG.copy()
        merged.update(conf)
        return merged
    else:
        return DEFAULT_CONFIG.copy()


# ----------
# Logging
# ----------
def setup_logging(logfile="sender.log"):
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt,
                        handlers=[logging.FileHandler(logfile, encoding="utf-8"),
                                  logging.StreamHandler()])
    logging.info("Logger inicializado.")


# -------------------
# Validation & Utils
# -------------------
def normalize_phone(raw: str) -> Optional[str]:
    """Remove caracteres não numéricos e valida um formato simples.
    Retorna string só com dígitos ou None se inválido.
    """
    if pd.isna(raw):
        return None
    s = "".join(ch for ch in str(raw) if ch.isdigit())
    # Ex: considerar números internacionais com DDI (padrão mínimo 10 dígitos)
    if len(s) < 10:
        return None
    return s


def within_send_windows(cfg: dict, now: Optional[datetime] = None) -> bool:
    """Checa se o horário atual está dentro de alguma janela configurada."""
    now = now or datetime.now()
    current = now.time()
    for start_s, end_s in cfg["send_windows"]:
        start = datetime.strptime(start_s, "%H:%M").time()
        end = datetime.strptime(end_s, "%H:%M").time()
        if start <= current <= end:
            return True
    return False


def human_sleep(min_s: float, max_s: float, cfg: dict):
    """Espera um tempo aleatório dividido em chunks, com possibilidade de ações periódicas."""
    total = random.uniform(min_s, max_s)
    elapsed = 0.0
    while elapsed < total:
        # chunk curtinho para poder executar ações periódicas
        chunk = random.uniform(2.0, min(10.0, total - elapsed))
        time.sleep(chunk)
        elapsed += chunk
        # possibilidade de executar ação periódica
        if cfg.get("perform_periodic_actions") and random.random() < cfg.get("periodic_action_probability", 0.3):
            try:
                # action is best-effort: oculta exceções
                perform_random_periodic_action_safe()
            except Exception as ex:
                logging.debug(f"Periodic action failed silently: {ex}")
    logging.debug(f"Humanoid sleep total={total:.2f}s")


# -----------------------------------
# Periodic UI simulation (best-effort)
# -----------------------------------
# NOTE: the real implementation needs driver context; here we provide a safe no-driver fallback
_global_driver_for_periodic_action = None  # set later when driver is available


def perform_random_periodic_action_safe():
    """Chama a ação periódica se houver driver disponível (best-effort)."""
    driver = _global_driver_for_periodic_action
    if driver is None:
        # sem driver, nada a fazer
        return
    try:
        perform_random_periodic_action(driver)
    except Exception:
        # falha silenciosa: não interromper o fluxo principal
        pass


def perform_random_periodic_action(driver):
    """
    Simula pequenas interações: scrolls, abrir/fechar search, mover o cursor.
    Use com cuidado: elemento IDs/XPath podem precisar de ajuste.
    """
    def action_scroll():
        try:
            side_panel = driver.find_element(By.ID, "side")
            scroll_amount = random.randint(-300, 300)
            driver.execute_script("arguments[0].scrollTop += arguments[1];", side_panel, scroll_amount)
            logging.debug("Simulação: rolagem")
        except Exception:
            raise

    def action_click_search():
        try:
            search_box_xpath = "//div[@id='side']//div[@role='textbox']"
            search_box = driver.find_element(By.XPATH, search_box_xpath)
            search_box.click()
            time.sleep(random.uniform(0.4, 1.2))
            search_box.send_keys(Keys.ESCAPE)
            logging.debug("Simulação: clique na pesquisa")
        except Exception:
            raise

    def action_scroll_chat_messages():
        try:
            # Tenta encontrar o painel de mensagens da conversa
            # Este seletor é mais robusto para a área de mensagens
            chat_panel = driver.find_element(By.XPATH, "//div[@data-testid='conversation-panel-messages']")
            scroll_amount = random.randint(-500, 500) # Rola para cima ou para baixo
            driver.execute_script("arguments[0].scrollTop += arguments[1];", chat_panel, scroll_amount)
            logging.debug("Simulação: rolagem da conversa")
        except Exception:
            # Se o painel de mensagens não estiver visível (ex: tela inicial), falha silenciosamente
            raise

    actions = [action_scroll, action_click_search, action_scroll_chat_messages]
    random.choice(actions)()


# -----------------------
# Typing / humanization
# -----------------------
def human_type(element, text: str, cfg: dict):
    """Simula digitação humana caractere por caractere, com pauses, hesitações e correções."""
    min_delay = cfg.get("typing_delay_min", 0.03)
    max_delay = cfg.get("typing_delay_max", 0.12)
    correction_prob = cfg.get("correction_probability", 0.04)
    pause_prob = cfg.get("pause_probability", 0.06)

    for ch in text:
        element.send_keys(ch)
        # pequenas variações no delay
        time.sleep(random.uniform(min_delay, max_delay))
        # às vezes, faz uma pequena pausa "pensando"
        if random.random() < pause_prob:
            time.sleep(random.uniform(0.2, 1.2))


# -------------------
# Sending primitives
# -------------------
def send_whatsapp_message(driver, phone_number: str, message: str, cfg: dict) -> bool:
    """Navega para a conversa e envia a mensagem usando o método de copiar/colar."""
    wait_seconds = cfg.get("webdriver_wait_seconds", 40)
    try:
        logging.info(f"Preparando envio para {phone_number} (método de colar)")
        chat_url = f"https://web.whatsapp.com/send?phone={phone_number}"
        driver.get(chat_url)
        
        wait = WebDriverWait(driver, wait_seconds)
        message_box_xpath = "//footer//div[@role='textbox']"
        message_box = wait.until(EC.presence_of_element_located((By.XPATH, message_box_xpath)))

        # Pausa antes de colar
        time.sleep(random.uniform(1.5, 3.0))

        # Lógica de Copiar e Colar
        pyperclip.copy(message)
        message_box.send_keys(Keys.CONTROL, 'v') # Simula Ctrl+V
        logging.info(f"Mensagem colada para {phone_number}")

        # Pausa final antes de enviar
        time.sleep(random.uniform(0.5, 1.0))
        message_box.send_keys(Keys.ENTER)

        time.sleep(random.uniform(2.0, 4.0))
        logging.info(f"Enviado para {phone_number}")
        return True

    except Exception as e:
        logging.warning(f"Erro ao enviar para {phone_number}: {type(e).__name__} {e}")
        try:
            popup = driver.find_element(By.XPATH, "//div[@data-testid='popup-contents']")
            logging.debug(f"Popup detectado: {popup.text[:200]}")
        except Exception:
            pass
        return False


# -----------------
# Retry decorator
# -----------------
def retry_with_backoff(attempts=3, base_delay=3.0):
    def deco(func):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    sleep_time = base_delay * (2 ** (attempt - 1)) * random.uniform(0.8, 1.2)
                    logging.warning(f"Attempt {attempt}/{attempts} failed: {e}. Backing off {sleep_time:.1f}s")
                    time.sleep(sleep_time)
            logging.error(f"All {attempts} attempts failed for {func.__name__}. Last error: {last_exc}")
            raise last_exc
        return wrapper
    return deco


# -------------------
# Checkpoint helpers
# -------------------
def save_checkpoint(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# -------------------------
# High-level send manager
# -------------------------
class SafeSender:
    def __init__(self, driver, cfg: dict):
        self.driver = driver
        self.cfg = cfg
        self.sent_log_file = cfg["sent_log_file"]
        self.checkpoint_file = cfg["checkpoint_file"]
        self.hourly_count = 0
        self.daily_count = 0
        # load checkpoint
        self.checkpoint = load_checkpoint(self.checkpoint_file)
        # global driver used by periodic actions
        global _global_driver_for_periodic_action
        _global_driver_for_periodic_action = driver

    def load_contacts(self) -> pd.DataFrame:
        file = self.cfg["contacts_file"]
        df = pd.read_excel(file)
        df = df.dropna(subset=['CONTATO'])  # drop rows sem contato
        # normalize
        df['CONTATO'] = df['CONTATO'].apply(lambda r: normalize_phone(r))
        df = df.dropna(subset=['CONTATO'])
        # remove already sent (persistidos no arquivo de enviados)
        if os.path.exists(self.sent_log_file):
            df_sent = pd.read_excel(self.sent_log_file)
            sent_set = set(df_sent['CONTATO'].astype(str))
            df = df[~df['CONTATO'].astype(str).isin(sent_set)].copy()
        # randomize order if configured
        if self.cfg.get("randomize_order", True):
            df = df.sample(frac=1).reset_index(drop=True)
        return df

    def can_send_now(self) -> bool:
        # checar janelas e limites
        if not within_send_windows(self.cfg):
            logging.info("Fora das janelas de envio configuradas.")
            return False
        # checar rate limits
        # Nota: aqui usamos counters simples resetados a cada hora/dia
        # (melhoria: persistir counters entre runs)
        return True

    def update_counters(self, n=1):
        self.hourly_count += n
        self.daily_count += n

    def persist_sent(self, sent_records: List[Dict[str, str]]):
        # atualiza o arquivo de enviados (append)
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
        logging.info(f"Persistidos {len(sent_records)} envios em {self.sent_log_file}")

    @retry_with_backoff(attempts=3, base_delay=3.0)
    def safe_send_once(self, contato: str, mensagem: str) -> bool:
        return send_whatsapp_message(self.driver, contato, mensagem, self.cfg)

    def run(self):
        df = self.load_contacts()
        logging.info(f"Contatos carregados para envio: {len(df)}")
        sent_records = []

        # resume support: skip indices processed (checkpoint stores last_index)
        last_index = self.checkpoint.get("last_index", -1)

        for idx, row in df.reset_index(drop=True).iterrows():
            # checkpoint check
            if idx <= last_index:
                logging.debug(f"Pulando idx {idx} (já processado segundo checkpoint).")
                continue

            nome = row.get('NOME', '').strip()
            contato = str(row['CONTATO'])
            mensagem = generate_dynamic_message(nome)


            # wait until send window available
            if not self.can_send_now():
                logging.info("Aguardando janela de envio...")
                # poll até ficar dentro da janela (com backoff para economizar CPU)
                while not within_send_windows(self.cfg):
                    # salva checkpoint antes de dormir
                    save_checkpoint(self.checkpoint_file, {"last_index": idx - 1})
                    time.sleep(60)
                logging.info("Janela de envio iniciada, retomando.")

            # rate limit enforcement (simple)
            if self.hourly_count >= self.cfg.get("max_messages_per_hour", 60):
                logging.info("Limite horário atingido. Esperando 10 minutos.")
                human_sleep(600, 600, self.cfg)  # espera 10 minutos
                self.hourly_count = 0  # simplificação: reset manual
            if self.daily_count >= self.cfg.get("max_messages_per_day", 300):
                logging.warning("Limite diário atingido. Encerrando execucao.")
                break

            # safe send with retries
            success = False
            try:
                success = self.safe_send_once(contato, mensagem)
            except Exception as e:
                logging.error(f"Envio falhou permanentemente para {contato}: {e}")
                success = False

            if success:
                sent_records.append({"NOME": nome, "CONTATO": contato, "TIMESTAMP": datetime.now().isoformat()})
                self.update_counters(1)

            # checkpoint after each contact
            save_checkpoint(self.checkpoint_file, {"last_index": idx})
            logging.debug(f"Checkpoint salvo: idx={idx}")

            # intervalo humanizado entre envios (min..max)
            if idx < len(df) - 1:
                human_sleep(self.cfg["min_interval_seconds"], self.cfg["max_interval_seconds"], self.cfg)

        # persist all sent in this run
        if sent_records:
            self.persist_sent(sent_records)
        logging.info("Execução finalizada do SafeSender.")


# -----------------------
# Browser setup wrapper
# -----------------------
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


# -----------------------
# Entrypoint principal
# -----------------------
def main():
    cfg = load_config("config.json")
    setup_logging(cfg.get("log_file", "sender.log"))
    logging.info("Carregando webdriver...")
    driver = create_webdriver(cfg["profile_dir"])
    try:
        driver.get("https://web.whatsapp.com")
        wait = WebDriverWait(driver, 90)
        logging.info("Aguardando login no WhatsApp Web (escaneie o QR code se necessário)...")
        wait.until(EC.presence_of_element_located((By.ID, "side")))
        logging.info("Login detectado.")

        sender = SafeSender(driver, cfg)
        sender.run()

    except Exception as main_exc:
        logging.exception("Erro crítico na execução principal: %s", main_exc)
    finally:
        # Opcional: esperar um pouco antes de fechar para inspeção final
        time.sleep(10)
        driver.quit()
        logging.info("Webdriver finalizado.")


if __name__ == "__main__":
    main()
