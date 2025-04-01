import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from BinaryOptionsTools.platforms.pocketoption.api import PocketOptionAPI

# **🔹 Configurazione manuale**
trade_mode = "DEMO"  # Può essere "DEMO" o "REAL"
SSID = "bc3b9995-ab06-4685-8de2-01897d363c8e"
importo_iniziale = 1
direzione = "BUY"
tipo_asset = "OTC"
fattore_incremento = 1.1
max_incremento = 2
incremento_fisso = 1.5
margine_richiesto = 2
minimo_payout = 90
scadenza = 10
take_profit = 1000
stop_loss = 200
max_losses = 3
adatta_importo = "OFF"
orari_di_lavoro = "09:00-12:00,14:00-18:00"
pausa = "1-15"
pause_attive = "ON"

# **🔹 Connessione all'API**
account = PocketOptionAPI(SSID, trade_mode)
input("\nPremi INVIO per continuare 1 ...")
#if not account.connect():
#    input("\nPremi INVIO per continuare 2 ...")
#    print("⛔ Connessione non riuscita. Esco...")

print("✅ Connessione API riuscita!")
input("\nPremi INVIO per continuare 3 ...")
# sys.exit()
# **🔹 Variabili di lavoro**
trade_amount = importo_iniziale
saldo_iniziale = 0
saldo_attuale = 0
payout_attuale = 0
perdite_consecutive = 0
saldo_sessione = 0

# Funzione che legge i dati di saldo, trade_amount e payout

def get_trading_data():
    """Recupera saldo e payout con delay per evitare blocchi API"""
    try:
        time.sleep(1)
        balance = account.get_balance()
        payout = account.get_payout()
        if payout :< minimo_payout:
            asset = get_best_asset()
        print(f"✅ Saldo: {balance}, Payout: {payout}%", Asset: {asset} )
        return float(balance), int(payout), asset
    except Exception as e:
        print(f"❌ Errore nel recupero dati trading: {e}")
        return None, None, None

def get_best_asset():
    """Seleziona il primo asset disponibile con payout più alto, evitando l'asset attivo"""
    try:
        assets = account.get_assets()
        sorted_assets = sorted(assets.items(), key=lambda x: x[1]["payout"], reverse=True)

        asset_attuale = account.get_active_asset()  # Supponiamo che questa API esista

        nuovo_asset = None
        for asset, data in sorted_assets:
            if asset != asset_attuale and data["open"]:
                nuovo_asset = asset
                break

        if nuovo_asset:
            print(f"✅ Nuovo asset selezionato: {nuovo_asset}")
            return nuovo_asset
        else:
            print("⚠️ Nessun nuovo asset disponibile, mantengo l'attuale.")
            return asset_attuale

    except Exception as e:
        print(f"❌ Errore nella selezione dell'asset: {e}")
        return asset_attuale

# Funzione per piazzare un trade

def place_trade(direzione, trade_amount):
    """Piazza un trade utilizzando l'API."""
    try:
        asset = tipo_asset
        duration = scadenza
        trade_info = account.place_trade(asset, trade_amount, direzione, duration)
        print(f"✅ Trade {direzione.upper()} eseguito con importo {trade_amount}")
        time.sleep(duration)
        return trade_info
    except Exception as e:
        print(f"❌ Errore nel piazzamento del trade: {e}")
        return None

def primo_trade():
    global saldo_iniziale, saldo_attuale, trade_amount
    saldo_iniziale, _ = get_trading_data()
    if saldo_iniziale is None:
        return
    trade_amount = importo_iniziale
    place_trade(direzione, trade_amount)
    time.sleep(scadenza)
    saldo_attuale, _ = get_trading_data()
    if saldo_attuale is None:
        return
    if saldo_attuale < saldo_iniziale:
        print("❌ Trade perso, avvio Martingala...")
        perdite_consecutive = 1
        if perdite_consecutive == max_losses:
            direzione = "SELL" if direzione == "BUY" else "BUY"

        # Incremento del trade_amount
        if fattore_incremento:
            trade_amount = round(float(trade_amount) * float(fattore_incremento), 2)
        else:
            trade_amount = round(float(trade_amount) + float(incremento_fisso), 2)
    else:
        print("✅ Trade vinto, riprendo ciclo...")
        primo_trade()

def martingala():
    global saldo_iniziale, saldo_single, trade_amount, perdite_consecutive, saldo_attuale 
    payout_attuale, profitto, prof_sessione

    ciclo_martingala = True
    while ciclo_martingala:
        saldo_single = saldo_attuale  # Per stabilire la singola perdita o vincita

        place_trade(direzione, trade_amount)
        saldo_attuale, _= get_trading_data()

        if saldo_attuale is None or trade_amount is None or payout_attuale is None:
            print("❌ Errore nel recupero dei dati di trading, riprovo...")
            time.sleep(2)
            continue

#        direzione = inverti_direzione()
        
        try:
            saldo_attuale = float(saldo_attuale)

            profitto = saldo_attuale - saldo_iniziale
            prof_sessione = saldo_attuale - saldo_sessione
 
            if saldo_single > saldo_attuale:
                perdite_consecutive += 1
                # Incremento del trade_amount
                incremento == fattore_incremento * trade_amount - trade_amount
                if incremento <= max_incremento and fattore_incremento:
                    trade_amount = round(float(trade_amount) * float(fattore_incremento), 2)
                else:
                    trade_amount = round(float(trade_amount) + float(incremento_fisso), 2)
                if perdite_consecutive == max_losses:
                    direzione = "SELL" if direzione == "BUY" else "BUY"
            else:
                perdite_consecutive = 0

            print(f"✍️ perdite_consecutive = {perdite_consecutive}")        

            if profitto >= float(config["margine_richiesto"]):
                print("\n✅ Margine richiesto raggiunto, reset della strategia!")
                trade_amount = importo_iniziale
                saldo_iniziale = saldo_attuale  # Aggiorna il saldo iniziale
                perdite_consecutive = 0
                profitto = 0

                ciclo_martingala = False
                break
        
            if prof_sessione <= -stop_loss or prof_sessione >= take_profit:
                print("\n⛔ Stop loss o take profit raggiunto, fermo il bot!")
                break
 
            if perdite_consecutive >= float(config["max_losses"]):
                print("\n⚠️ Troppi trade persi, seleziono un nuovo asset...")
                get_best_asset()
                perdite_consecutive = 0
                continue

        except ValueError:
            continueaccount = PocketOptionAPI(SSID, trade_mode)

# Funzione principale
def main():
    global saldo_sessione, saldo_iniziale, payout_attuale
    saldo_iniziale, payout_attuale, asset = get_trading_data()
    print(f"💰 Saldo iniziale: {saldo_iniziale}, Payout: {payout_attuale}")
    if saldo_iniziale is None:
        print("⚠️ Errore: impossibile recuperare il saldo iniziale. Uscita dal bot.")
        return
    saldo_sessione = saldo_iniziale
    primo_trade()

main()
#====================================================================

#***********************************************************************
