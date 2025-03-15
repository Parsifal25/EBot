import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys  # Importazione corretta per usare Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

# Porta di connessione al browser esistente
debug_port = 9222

# Carica i parametri dal file di configurazione
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as file:
            content = file.read().strip()
            if not content:
                raise ValueError("Il file di configurazione è vuoto!")
            config = json.loads(content)
        print("\n✅ Configurazione caricata correttamente!")
        return config
    except Exception as e:
        print(f"\n❌ Errore nel caricamento della configurazione: {e}")
        return {}

def update_config(key, value):
    """Aggiorna un valore nel file config.json e lo salva."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            config = json.load(file)
        
        config[key] = value  # Modifica il valore della chiave specificata
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)
        
        print(f"\n✅ Configurazione aggiornata: {key} -> {value}")
    except Exception as e:
        print(f"\n❌ Errore durante l'aggiornamento della configurazione: {e}")

# Caricamento dei parametri di configurazione
config = load_config()
tipo_asset = config.get("tipo_asset", "OTC")
importo_iniziale = config.get("importo_iniziale", 1)
direzione = config.get("direzione", "BUY")
fattore_incremento = config.get("fattore_incremento", 1.1)
incremento_fisso = config.get("incremento_fisso", 1.50)
margine_richiesto = config.get("margine_richiesto", 2)
minimo_payout = config.get("minimo_payout", 90)
scadenza = config.get("scadenza", 10)
inverti_se_perde = config.get("inverti_se_perde", "OFF")
inverti_se_vince = config.get("inverti_se_vince", "OFF")
take_profit = config.get("take_profit", 1000)
stop_loss = config.get("stop_loss", 200)
max_losses = config.get("max_losses", 5)
adatta_importo = config.get("adatta_importo", "OFF")
orari_di_lavoro = config.get("orari_di_lavoro", "09:00-12:00,14:00-18:00")
pausa = config.get("pausa", "1-15")
pause_attive = config.get("pause_attive", "OFF")
buy_button = config.get("buy_button", None)

sell_button = config.get("sell_button", None)


# Variabili di lavoro
saldo_sessione = 0
trade_amount = importo_iniziale
saldo_iniziale = 0
saldo_attuale = 0
payout_attuale = 0
perdite_consecutive = 0

# Funzione per agganciarsi a un browser già aperto
def connect_to_existing_browser():
    try:
        options = webdriver.ChromeOptions()
        options.debugger_address = f"localhost:{debug_port}"
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        print("\n✅ Connessione al browser esistente riuscita!")
        return driver
    except Exception as e:
        print(f"\n❌ Errore nella connessione al browser: {e}")
        return None

# Funzione che legge i dati di saldo, trade_amount e payout
def get_trading_data(driver):
    global trade_amount, amount_letto

    try:
        saldo_xpath = "//div[contains(@class, 'balance-info-block__balance')]/span"
        importo_xpath = "//div[contains(@class, 'value__val')]/input"
        payout_xpath = "//div[contains(@class, 'value__val-start')]"

        saldo_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, saldo_xpath)))
        saldo_text = saldo_element.text.strip().replace(',', '')

        importo_element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, importo_xpath)))
        amount_letto_text = importo_element.get_attribute("value").replace(',', '')

        payout_element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, payout_xpath)))
        payout_text = payout_element.text.strip().replace('+', '').replace('%', '')

        return float(saldo_text), amount_letto_text, int(payout_text)

    except Exception as e:
        print(f"\n❌ Errore nel recupero dati trading: {e}")
        driver.save_screenshot("error_get_data.png")
        return None, None, None
#************************************************************
def get_active_asset(driver):
    try:
        active_asset_xpath = "//*[@id='bar-chart']/div/div/div/div/div[1]/div[1]/div[1]/div/a/span"
        active_asset_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, active_asset_xpath))
        )
        active_asset = active_asset_element.text.strip()
        print(f"\n✅ Asset attivo recuperato: {active_asset}")
        return active_asset
    except Exception as e:
        print(f"\n❌ Errore nel recupero dell'asset attivo: {e}")
        driver.save_screenshot("error_active_asset.png")
        return None

def select_first_asset(driver, active_asset=None):
    try:
        print(f"\n🔍 Selezionando un asset OTC diverso da asset attivo: {active_asset}")
        
        dropdown_xpath = "//*[@id='bar-chart']/div/div/div/div/div[1]/div[1]/div[1]/div/a/div/i"
        asset_list_xpath = "//div[contains(@class, 'drop-down-modal-wrap')]//ul/li"
        
        # Aspetta che il menu sia cliccabile
        dropdown_element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, dropdown_xpath)))

        # Chiude eventuali drop-down aperti per evitare che blocchino il clic
        try:
            driver.execute_script("arguments[0].click();", dropdown_element)
            time.sleep(1)
        except Exception as e:
            print("\n⚠️ Il menu a discesa era già aperto o non è stato possibile cliccarlo.")

        dropdown_element.click()  # Clicca il menu a discesa per aprire la lista
        time.sleep(2)  # Attendi il caricamento della lista
        
        assets = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, asset_list_xpath)))
        selected_asset = None
        
        for asset in assets:
            asset_text = asset.text.upper()
            if "OTC" in asset_text and (active_asset is None or asset_text != active_asset.upper()):
                selected_asset = asset
                break
        
        if selected_asset:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", selected_asset)
                time.sleep(1)
                selected_asset.click()
                print(f"\n✅ Asset selezionato: {selected_asset.text}")
            except:
                driver.execute_script("arguments[0].click();", selected_asset)
        else:
            print("\n⚠️ Nessun asset OTC disponibile diverso dall'attivo.")
            
    except Exception as e:
        print(f"\n❌ Errore nella selezione dell'asset: {e}")
        driver.save_screenshot("error_select_asset.png")

#*****************************************************
# Funzione per creare bottoni e restituire gli elementi
def crea_bottoni(driver):
    try:
        print("\n🔍 Cercando pulsanti BUY e SELL...")
        
        buy_button = None
        sell_button = None
        
        for _ in range(3):  # Ritenta fino a 3 volte in caso di errore "stale element reference"
            try:
                buttons = WebDriverWait(driver, 10, poll_frequency=0.5).until(EC.presence_of_all_elements_located((By.XPATH, "//button | //a")))
                
                for btn in buttons:
                    btn_text = btn.text.strip().upper()
                    if "BUY" in btn_text:
                        buy_button = btn
                    elif "SELL" in btn_text:
                        sell_button = btn
                
                if buy_button and sell_button:
                    print("\n✅ Bottoni acquisiti con successo!")
                    return buy_button, sell_button
                
            except Exception as e:
                print(f"\n⚠️ Tentativo fallito ({_+1}/3) nel recupero dei bottoni: {e}")
                time.sleep(1)
        
        driver.save_screenshot("error_buttons_not_found.png")
        raise Exception("Bottoni BUY o SELL non trovati nella pagina.")
    except Exception as e:
        print(f"\n❌ Errore nell'acquisizione dei bottoni: {e}")
        return None, None        


# Funzione per piazzare un trade
def piazza_trade(driver, buy_button, sell_button):

    global trade_amount, scadenza

    try:
        trade_button = buy_button if direzione.upper() == "BUY" else sell_button
        
        if not trade_button:
            print("\n⚠️ Nessun pulsante valido trovato per il trade!")
            driver.save_screenshot("error_buttons.png")
            return

        saldo_attuale, amount_letto, payout_attuale = get_trading_data(driver)

#        print(f"\n💰 saldo-iniziale letto da piazza_trade = {saldo_iniziale}")
#        print(f"\n💰 saldo-attuale letto da piazza_trade = {saldo_attuale}")
#        print(f"🎯 payout letto da piazza_trade {payout_attuale}%")
#        print(f"\n💰 amount_letto letto da piazza_trade = {amount_letto}")
#        print(f"\n💰 trade_amount attuale da piazza_trade = {trade_amount}")

        if payout_attuale < minimo_payout:
             select_first_asset(driver)

#    registrazione trade_amount nella piattaforma
        importo_xpath = "//div[contains(@class, 'value__val')]/input"
        importo_element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, importo_xpath)))
        importo_element.send_keys(Keys.CONTROL, 'a')  # Seleziona tutto
        importo_element.send_keys(Keys.DELETE)  # Cancella 
        importo_element.send_keys(str(trade_amount))                

#        input("\nPremi INVIO per piazzare questo trade...")
        try:
            ActionChains(driver).move_to_element(trade_button).click().perform()
#            print(f"\n🛒 appena sparato trade di {trade_amount} in direzione {direzione}")
#            time.sleep(scadenza)

        except:
            try:
                driver.execute_script("arguments[0].click();", trade_button)
                print("\n✅ Trade inviato con JavaScript!")
            except:
                print("\n❌ Impossibile cliccare il pulsante di trade!")
                return
        
#        driver.save_screenshot("post_trade.png")
        
    except Exception as e:
        print(f"\n❌ Errore nell'esecuzione del trade: {e}")
#        driver.save_screenshot("error_trade.png")  # Salva screenshot per debugging

def primo_trade(driver, buy_button, sell_button):
    global saldo_iniziale, trade_amount, direzione, amount_letto, saldo_sessione

    trade_amount = importo_iniziale  
    saldo_iniziale, amount_letto, payout_attuale = get_trading_data(driver)

    if saldo_iniziale is None or trade_amount is None or payout_attuale is None:
        print("❌ Errore nel recupero dei dati di trading, riprovo...")

    while True:
        piazza_trade(driver, buy_button, sell_button)

        saldo_attuale, amount_letto, payout_attuale = get_trading_data(driver)

        if saldo_attuale is None or trade_amount is None or payout_attuale is None:
            print("❌ Errore nel recupero dei dati di trading, riprovo...")
            continue

        prof_sessione = saldo_attuale - saldo_sessione
        if prof_sessione <= -stop_loss or prof_sessione >= take_profit:
            print("\n⛔ Stop loss o take profit raggiunto, fermo il bot!")
            break

            print(f"\n🛒 trade_amount {trade_amount} S. iniz {saldo_iniziale} S. att {saldo_attuale}")

        if saldo_attuale < saldo_iniziale:
            print("\n❌ Trade perso, avvio strategia Martingala...")
            martingala(driver, buy_button, sell_button)
            return primo_trade(driver, buy_button, sell_button)  # Riparte dopo la Martingala
        else:
            print("\n✅ Trade vinto, continuo con il primo trade...")
            saldo_iniziale = saldo_attuale  # Aggiorna il saldo iniziale
            return primo_trade(driver, buy_button, sell_button)  # Riparte

def martingala(driver, buy_button, sell_button):
    global saldo_single, saldo_iniziale, trade_amount, perdite_consecutive, saldo_attuale, saldo_sessione, importo_iniziale
    print("\ndentro strategia Martingala...")
    ciclo_martingala = True
    amount_letto = 1
    while ciclo_martingala:
        try:

            # Incremento del trade_amount
 
            if fattore_incremento:
                trade_amount = round(float(trade_amount) * float(fattore_incremento), 2)
            else:
                trade_amount = round(float(trade_amount) + float(incremento_fisso), 2)
         
        except ValueError as ve:
            print(f"❌ Errore di valore: {ve}")
            continue
        except Exception as e:
            print(f"❌ Errore inatteso nell'incremento dell'importo: {e}")
            continue
        
        saldo_single = saldo_attuale  # Per stabilire la singola perdita o vincita

        piazza_trade(driver, buy_button, sell_button)
        
        saldo_attuale, amount_letto, payout_attuale = get_trading_data(driver)

        if saldo_attuale is None or trade_amount is None or payout_attuale is None:
            print("❌ Errore nel recupero dei dati di trading, riprovo...")
            continue
        if inverti_se_perde == "ON" or inverti_se_vince == "ON":        
            direzione = inverti_direzione(driver)
        
        saldo_attuale = float(saldo_attuale)
        profitto = saldo_attuale - saldo_iniziale
        prof_sessione = saldo_attuale - saldo_sessione
 
        if saldo_single > saldo_attuale:
            perdite_consecutive += 1
            print(f"✍️ perdite_consecutive = {perdite_consecutive}")        
            if perdite_consecutive >= max_losses:
                print("\n⚠️ Troppi trade persi, seleziono un nuovo asset...")
                attivo = get_active_asset(driver)
                select_first_asset(driver, attivo)
                perdite_consecutive = 0
        else:
            perdite_consecutive = 0

        if prof_sessione <= -stop_loss or prof_sessione >= take_profit:
            print("\n⛔ Stop loss o take profit raggiunto, fermo il bot!")
            break

        if profitto >= float(margine_richiesto):
            print("\n✅ Margine richiesto raggiunto, reset della strategia!")
            trade_amount = importo_iniziale
            saldo_iniziale = saldo_attuale  # Aggiorna il saldo iniziale
            perdite_consecutive = 0
            trade_amount = importo_iniziale
            profitto = 0
            ciclo_martingala = False
            break
        
#        except ValueError:
#            continue

# Funzione principale
def main():
    global saldo_sessione, saldo_iniziale, amount_letto, payout_attuale, buy_button, sell_button

    driver = connect_to_existing_browser()
    if driver is None:
        return

    select_first_asset(driver, "cambio")

#    if not buy_button or not sell_button:
    buy_button, sell_button = crea_bottoni(driver)
    if not buy_button or not sell_button:
        print("\n❌ Errore nel recupero dei bottoni, impossibile continuare.")
        return

    saldo_iniziale, amount_letto, payout_attuale = get_trading_data(driver)
    saldo_sessione = float(saldo_iniziale)

    primo_trade(driver, buy_button, sell_button)

if __name__ == "__main__":
    main()

#====================================================================
