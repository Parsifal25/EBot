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
tot_losses = 30%
adatta_importo = "OFF"
orari_di_lavoro = "09:00-12:00,14:00-18:00"
pausa = "1-15"
pause_attive = "ON"

# **🔹 Connessione all'API**
account = PocketOptionAPI(SSID, trade_mode)
input("\nPremi INVIO per continuare...")

print("✅ Connessione API riuscita!")

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
        asset = get_best_asset(False)
        print(f"✅ Saldo: {balance}, Payout: {payout}%, Asset: {asset}")
        return float(balance), int(payout), asset
    except Exception as e:
        print(f"❌ Errore nel recupero dati trading: {e}")
        return None, None, None

def get_best_asset(cambio):
    """
    Seleziona il miglior asset disponibile con payout più alto e conforme al tipo_asset.
    Se il tipo_asset è "OTC", seleziona solo asset con "OTC" nel nome.
    """
    try:
        assets = account.get_assets()
        
        # Filtra gli asset in base al tipo specificato
        if tipo_asset == "OTC":
            filtered_assets = {asset: data for asset, data in assets.items() if "OTC" in asset}
        else:
            filtered_assets = {asset: data for asset, data in assets.items() if "OTC" not in asset}

        # Ordina gli asset filtrati per payout decrescente
        sorted_assets = sorted(filtered_assets.items(), key=lambda x: x[1]["payout"], reverse=True)
        
        asset_attuale = account.get_active_asset()
        
        # Controlla se il payout dell'asset attuale è inferiore al minimo_payout o se è richiesto il cambio
        if cambio or assets[asset_attuale]['payout'] < minimo_payout:
            for asset, data in sorted_assets:
                if asset != asset_attuale and data["open"]:
                    print(f"✅ Nuovo asset selezionato: {asset}")
                    return asset
            print("⚠️ Nessun nuovo asset disponibile del tipo specificato, mantengo l'attuale.")
            return asset_attuale
        else:
            print(f"⚠️ Payout attuale ({assets[asset_attuale]['payout']}%) è sufficiente, mantengo l'asset attuale.")
            return asset_attuale

    except Exception as e:
        print(f"❌ Errore nella selezione dell'asset: {e}")
        return asset_attuale

def primo_trade():
    global saldo_iniziale, saldo_attuale, trade_amount, perdite_consecutive, direzione
    saldo_iniziale, _, _ = get_trading_data()
    if saldo_iniziale is None:
        return
    trade_amount = importo_iniziale
    place_trade(direzione, trade_amount)
    time.sleep(scadenza)
    saldo_attuale, _, _ = get_trading_data()
    if saldo_attuale is None:
        return
    if saldo_attuale < saldo_iniziale:
        print("❌ Trade perso, avvio Martingala...")
        perdite_consecutive = 1
        if perdite_consecutive == max_losses:
            direzione = "SELL" if direzione == "BUY" else "BUY"
        trade_amount = round(float(trade_amount) * float(fattore_incremento), 2)
    else:
        print("✅ Trade vinto, riprendo ciclo...")
        primo_trade()

def martingala():
    global saldo_iniziale, saldo_attuale, trade_amount, perdite_consecutive, direzione
    tot_vinti = 0
    tot_persi = 1
    ciclo_martingala = True
    while ciclo_martingala:
        saldo_single = saldo_attuale
        place_trade(direzione, trade_amount)
        saldo_attuale, _, _ = get_trading_data()
        if saldo_attuale is None:
            print("❌ Errore nel recupero dati di trading, riprovo...")
            time.sleep(2)
            continue
        
        if saldo_single > saldo_attuale:
            perdite_consecutive += 1
            tot_persi += 1
            incremento = fattore_incremento * trade_amount - trade_amount
            if incremento <= max_incremento:
                trade_amount = round(float(trade_amount) * float(fattore_incremento), 2)
            else:
                trade_amount = round(float(trade_amount) + float(incremento_fisso), 2)
            if perdite_consecutive == max_losses:
                direzione = "SELL" if direzione == "BUY" else "BUY"
        else:
            perdite_consecutive = 0
            tot_vinti += 1
        
        if saldo_attuale - saldo_iniziale >= margine_richiesto:
            print("✅ Margine raggiunto, reset della strategia!")
            trade_amount = importo_iniziale
            saldo_iniziale = saldo_attuale
            perdite_consecutive = 0
            ciclo_martingala = False
            break
        
        if saldo_attuale - saldo_sessione <= -stop_loss or saldo_attuale - saldo_sessione >= take_profit:
            print("⛔ Stop loss o take profit raggiunto, fermo il bot!")
            break

        # se le perdite superano le vincite più della %ale ammessa si cambia asset
        totale_trade = tot_persi + tot_vinti
        if totale_trade <> 0:
            percentuale_persi = (tot_persi / totale_trade) * 100
        if percentuale_persi >= tot_losses:
            asset = get_best_asset(True)

#*********************************************
def main():
    global saldo_sessione, saldo_iniziale, payout_attuale
    asset = get_best_asset(True)
    saldo_iniziale, payout_attuale, _ = get_trading_data()
    print(f"💰 Saldo iniziale: {saldo_iniziale}, Payout: {payout_attuale}, Asset: {asset}")
    if saldo_iniziale is None:
        print("⚠️ Errore: impossibile recuperare il saldo iniziale. Uscita dal bot.")
        return
    saldo_sessione = saldo_iniziale
    primo_trade()

main()

#====================================================================

#***********************************************************************
