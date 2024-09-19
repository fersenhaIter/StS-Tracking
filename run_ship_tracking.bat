@echo off
REM Install required Python modules one by one
pip install json
pip install folium
pip install requests
pip install beautifulsoup4
pip install pandas
pip install geopandas
pip install shapely
pip install colorama
pip install openpyxl

REM Run the main Python program
python program.py

pause
