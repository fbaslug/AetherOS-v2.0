@echo off
echo Iniciando AetherOS v2.0...
set DISPLAY=localhost:0.0

:: Conectarse por SSH y lanzar el comando en Linux automáticamente
ssh -Y kali@192.168.32.128 "cd ~/AetherOS && python3 main.py"