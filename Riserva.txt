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

# Porta di connessione al browser esistente
debug_port = 9222

# Parametri generici
importo_iniziale = 1
direzione = "BUY"
tipo_asset = "OTC"
fattore_incremento = 1.09
incremento_fisso = 1.50
margine_richiesto = 2
minimo_payout = 90
scadenza = 10
inverti_se_perde = "OFF"
inverti_se_vince = "OFF"
take_profit = 100
stop_loss = 60
max_losses = 5
adatta_importo = "OFF"
orari_di_lavoro = "09:00-12:00,14:00-18:00"
pausa = "1-15"
pause_attive = "ON,OFF"

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

# Funzione per selezionare il primo asset dalla lista
def select_first_asset(driver):
    try:
        print("\n🔍 Selezionando il primo asset nella lista...")
        dropdown_xpath = "//*[@id='bar-chart']/div/div/div/div/div[1]/div[1]/div[1]/div/a/div/i"
        asset_list_xpath = "//div[contains(@class, 'drop-down-modal-wrap')]//ul/li"
        
        dropdown_element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, dropdown_xpath)))
        dropdown_element.click()
        
        time.sleep(2)  # Attendi il caricamento della lista
        
        assets = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.XPATH, asset_list_xpath)))
        selected_asset = None
        
        if tipo_asset.upper() == "OTC":
            for asset in assets:
                if "OTC" in asset.text.upper():
                    selected_asset = asset
                    break
        
        if not selected_asset:
            print("\n⚠️ Nessun asset OTC trovato, seleziono il primo disponibile...")
            selected_asset = assets[0]
        
        if selected_asset:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", selected_asset)
                time.sleep(1)
                selected_asset.click()
            except:
                driver.execute_script("arguments[0].click();", selected_asset)
            print("\n✅ Asset selezionato correttamente!")

#            dropdown_element.click()        
#        time.sleep(1)

    except Exception as e:
        print(f"\n❌ Errore nella selezione dell'asset: {e}")
        driver.save_screenshot("error_select_asset.png")

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

def inverti_direzione(driver):

    global saldo_single, saldo_attuale, direzione, inverti_se_perde, inverti_se_vince

    if saldo_single > saldo_attuale and inverti_se_perde == "ON":
        direzione = "SELL" if direzione == "BUY" else "BUY"
        print("🔄 Inversione di direzione per perdita, nuova direzione:", direzione)
    
    if saldo_single < saldo_attuale and inverti_se_vince == "ON":
        direzione = "SELL" if direzione == "BUY" else "BUY"
        print("🔄 Inversione di direzione per vincita, nuova direzione:", direzione)
    
    return direzione

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

#***************** Registrazione trade amount ********************************
        importo_xpath = "//div[contains(@class, 'value__val')]/input"
        importo_element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, importo_xpath)))
        importo_element.send_keys(Keys.CONTROL, 'a')  # Seleziona tutto
        importo_element.send_keys(Keys.DELETE)  # Cancella 
        importo_element.send_keys(str(trade_amount))                

#        input("\nPremi INVIO per piazzare questo trade...")
        try:
            ActionChains(driver).move_to_element(trade_button).click().perform()
            print(f"\n🛒 appena sparato trade di {trade_amount} in direzione {direzione}")
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

    while True:
        piazza_trade(driver, buy_button, sell_button)

        saldo_attuale, amount_letto, payout_attuale = get_trading_data(driver)

        if saldo_attuale is None or trade_amount is None or payout_attuale is None:
            print("❌ Errore nel recupero dei dati di trading, riprovo...")
            time.sleep(2)
            continue

        prof_sessione = saldo_attuale - saldo_sessione
        if prof_sessione <= -stop_loss or prof_sessione >= take_profit:
            print("\n⛔ Stop loss o take profit raggiunto, fermo il bot!")
            break

        if saldo_attuale < saldo_iniziale:
            print("\n❌ Trade perso, avvio strategia Martingala...")
            martingala(driver, buy_button, sell_button)
            return primo_trade(driver, buy_button, sell_button)  # Riparte dopo la Martingala
        else:
            print("\n✅ Trade vinto, continuo con il primo trade...")
            saldo_iniziale = saldo_attuale  # Aggiorna il saldo iniziale
            return primo_trade(driver, buy_button, sell_button)  # Riparte

def martingala(driver, buy_button, sell_button):
    global saldo_single, saldo_iniziale, trade_amount, perdite_consecutive, saldo_attuale, saldo_sessione

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
            time.sleep(2)
            continue

        direzione = inverti_direzione(driver)
        
        try:
            saldo_attuale = float(saldo_attuale)

            profitto = saldo_attuale - saldo_iniziale
            prof_sessione = saldo_attuale - saldo_sessione
 
            print(f"✍️ profitto = {profitto}")
            print(f"✍️ margine_richiesto = {margine_richiesto}")

        except ValueError:
            print("❌ Errore nella conversione del saldo attuale, valore non valido.")
            continue
        try:
            if saldo_single > saldo_attuale:
                perdite_consecutive += 1
            else:
                perdite_consecutive = 0
        
            if profitto >= float(margine_richiesto):
                print("\n✅ Margine richiesto raggiunto, reset della strategia!")
                trade_amount = importo_iniziale
                saldo_iniziale = saldo_attuale  # Aggiorna il saldo iniziale
                perdite_consecutive = 0
                profitto = 0
                ciclo_martingala = False
#                break
        
            if prof_sessione <= -stop_loss or prof_sessione >= take_profit:
                print("\n⛔ Stop loss o take profit raggiunto, fermo il bot!")
                break
 
            if perdite_consecutive >= max_losses:
                print("\n⚠️ Troppi trade persi, seleziono un nuovo asset...")
                select_first_asset(driver)
                perdite_consecutive = 0
                continue

        except ValueError:
            continue

# Funzione principale
def main():
    global saldo_sessione, saldo_iniziale, amount_letto, payout_attuale

    driver = connect_to_existing_browser()
    if driver is None:
        return

    buy_button, sell_button = crea_bottoni(driver)
    if not buy_button or not sell_button:
        print("\n❌ Errore nel recupero dei bottoni, impossibile continuare.")
        return
    select_first_asset(driver)
    saldo_iniziale, amount_letto, payout_attuale = get_trading_data(driver)
    saldo_sessione = float(saldo_iniziale)

    primo_trade(driver, buy_button, sell_button)

if __name__ == "__main__":
    main()