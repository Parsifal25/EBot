@echo off
title Avvio Trading Bot Pocket Option
echo Spostamento nella cartella EBot...
cd /d C:\EBot

echo Avvio di Google Chrome in modalità debug...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"

