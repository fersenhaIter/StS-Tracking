import json
import folium
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import pandas as pd
from math import radians, cos, sin, sqrt, atan2
import webbrowser
import geopandas as gpd
from shapely.geometry import Point
import colorama
from colorama import Fore, Style
from shapely.geometry import Polygon, Point, box
from folium import plugins

colorama.init()

DOWNLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')

class ShipDataAnalyzer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }

    def setup_directory(self, selected_area=None):
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        directory_name = f"data_{current_time}"
        os.makedirs(directory_name, exist_ok=True)
        
        if selected_area:
            self.create_map_html(directory_name, selected_area)
            self.save_geojson(directory_name, selected_area)
        
        return directory_name

    def load_data(self):
        json_path = os.path.join(DOWNLOAD_FOLDER, 'selected_area.geojson')
        while not os.path.exists(json_path):
            time.sleep(1)
        with open(json_path, 'r') as f:
            data = json.load(f)
        #print("Empfangene GeoJSON-Daten:", json.dumps(data, indent=2))
        os.remove(json_path)
        
        if data['type'] == 'FeatureCollection' and len(data['features']) > 0:
            feature = data['features'][0]
            geometry = feature['geometry']
            
            if geometry['type'] == 'Point':  # Für Kreise
                center = geometry['coordinates']
                try:
                    radius_km = float(feature['properties'].get('radius', 0))
                except ValueError:
                    print(f"Ungültiger Radius-Wert. Verwende 0 als Standard.")
                    radius_km = 0
                
                if radius_km > 0:
                    shape = Point(center).buffer(radius_km / 111.32)
                    minlon, minlat, maxlon, maxlat = shape.bounds
                else:
                    print("Radius ist 0 oder negativ. Verwende einen Punkt statt eines Kreises.")
                    minlon, minlat = maxlon, maxlat = center[0], center[1]
                    shape = Point(center)
            
            elif geometry['type'] == 'Polygon':  # Für Polygone und Rechtecke
                coordinates = geometry['coordinates'][0]
                shape = Polygon(coordinates)
                minlon, minlat, maxlon, maxlat = shape.bounds
            
            else:
                print(f"Unbekannter Geometrietyp: {geometry['type']}")
                return None

            return {
                'minlon': minlon, 'minlat': minlat, 'maxlon': maxlon, 'maxlat': maxlat,
                'shape': shape
            }
        else:
            print("Ungültiges GeoJSON-Format oder leere FeatureCollection.")
            return None

    def create_circle(self, lat, lon, radius_km):
        point = Point(lon, lat)
        circle = point.buffer(radius_km / 111.32)
        return gpd.GeoDataFrame(geometry=[circle], crs="EPSG:4326")

    def open_html_page(self):
        webbrowser.open('file://' + os.path.realpath('index.html'))

    def convert_coordinates(self, coord_str):
        coord_str = coord_str.replace('°', '').replace('N', '').replace('S', '-').replace('E', '').replace('W', '')
        try:
            return float(coord_str)
        except ValueError:
            print(f"Conversion error with string: {coord_str}")
            return 0.0

    def get_ships_in_area(self, selected_area):
        if not selected_area or not isinstance(selected_area, dict):
            print("Kein gültiger Bereich ausgewählt.")
            return {}

        minlon, minlat, maxlon, maxlat = selected_area['minlon'], selected_area['minlat'], selected_area['maxlon'], selected_area['maxlat']
        shape = selected_area['shape']

        url = f'https://www.myshiptracking.com/requests/vesselsonmaptempTTT.php?type=json&minlat={minlat}&maxlat={maxlat}&minlon={minlon}&maxlon={maxlon}&zoom=11&selid=-1&seltype=0&timecode=-1'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Fehler beim Abrufen der Daten: {e}")
            return {}

        vessels = {}
        content = response.text
        lines = content.split('\n')

        for line in lines:
            if not line.strip():
                continue
            try:
                data_list = line.split("\t")
                if len(data_list) >= 6:
                    mmsi = data_list[2]
                    lat = self.convert_coordinates(data_list[4])
                    lon = self.convert_coordinates(data_list[5])
                    point = Point(lon, lat)
                    
                    if shape.contains(point):
                        vessels[mmsi] = {
                            'latitude': lat,
                            'longitude': lon,
                            'name': data_list[0],
                            'type': data_list[1]
                        }
            except Exception as e:
                print(f"Fehler beim Verarbeiten einer Zeile: {e}")
                continue

        return vessels

    def get_ship_data(self, ship_id, directory):
        url = f"https://www.myshiptracking.com/vessels/{ship_id}-mmsi-{ship_id}-imo-"
        response = requests.get(url, headers=self.headers)
        html_content = response.text
        file_path = os.path.join(directory, f"{ship_id}.html")
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        soup = BeautifulSoup(html_content, 'html.parser')
        imo = self.get_ship_data_field(soup, "IMO")
        if not imo.replace("'","").isdigit():
            os.remove(file_path)
            return None

        fields = ["Type", "IMO", "MMSI", "Flag", "Call Sign", "Size", "GT", "DWT", "Build", "Longitude", "Latitude", "Status", "Speed", "Course", "Area", "Station", "Position Received", "Trip Time", "Trip Distance", "Average Speed", "Maximum Speed", "Draught"]
        ship_data = {field: self.get_ship_data_field(soup, field) for field in fields}

        ship_data['Most Visited Ports'] = self.extract_most_visited_ports(soup)
        ship_data['Last Trips'] = self.extract_last_trips(soup)
        ship_data['Port Calls'] = self.extract_port_calls(soup)

        return ship_data

    def get_ship_data_field(self, soup, field_name):
        result = soup.find(string=field_name)
        if result:
            next_td = result.find_next('td')
            if next_td:
                value = next_td.text.strip().replace('\u00b0', '').replace('N', '').replace('S', '-').replace('E', '').replace('W', '-')
                value = ''.join(c for c in value if c.isprintable())
                return value if value else "Nicht verfügbar"
        return "Nicht verfügbar"

    def process_html_files_in_directory(self, directory):
        vessels = {}
        for filename in os.listdir(directory):
            if filename.endswith(".html"):
                file_path = os.path.join(directory, filename)
                with open(file_path, 'r', encoding='utf-8') as file:
                    html_content = file.read()
                ship_id = filename.split('.')[0]
                soup = BeautifulSoup(html_content, 'html.parser')
                fields = ["Type", "IMO", "MMSI", "Flag", "Call Sign", "Size", "GT", "DWT", "Build", "Longitude", "Latitude", "Status", "Speed", "Course", "Area", "Station", "Position Received", "Trip Time", "Trip Distance", "Average Speed", "Maximum Speed", "Draught"]
                ship_data = {field: self.get_ship_data_field(soup, field) for field in fields}

                if ship_data['IMO'].replace("'","").isdigit():
                    ship_data['Most Visited Ports'] = self.extract_most_visited_ports(soup)
                    ship_data['Last Trips'] = self.extract_last_trips(soup)
                    ship_data['Port Calls'] = self.extract_port_calls(soup)
                    vessels[ship_id] = ship_data
                else:
                    os.remove(file_path)

        json_file_path = os.path.join(directory, "vessels.json")
        with open(json_file_path, 'w', encoding='utf-8') as file:
            json.dump(vessels, file, indent=4)
        print(f"Processed HTML files and saved data in {json_file_path}")

    def pair_nearby_ships(self, directory, distance_threshold=75, speed_threshold=None):
        json_file_name = os.path.join(directory, "vessels.json")
        with open(json_file_name, 'r') as file:
            data = json.load(file)

        ships = list(data.keys())
        paired_ships = []

        for i in range(len(ships)):
            for j in range(i + 1, len(ships)):
                ship1 = data[ships[i]]
                ship2 = data[ships[j]]

                if not self.is_valid_ship(ship1) or not self.is_valid_ship(ship2):
                    continue

                lat1, lon1 = self.convert_coordinates(ship1["Latitude"]), self.convert_coordinates(ship1["Longitude"])
                lat2, lon2 = self.convert_coordinates(ship2["Latitude"]), self.convert_coordinates(ship2["Longitude"])

                size1 = ship1.get("Size", "0 x 0") if ship1.get("Size", "---") not in ['---', '0 m'] else "0 x 0"
                size2 = ship2.get("Size", "0 x 0") if ship2.get("Size", "---") not in ['---', '0 m'] else "0 x 0"

                distance = self.calculate_rectangle_distance(lat1, lon1, size1, lat2, lon2, size2)

                if distance <= distance_threshold:
                    if speed_threshold:
                        speed1 = float(ship1.get("Speed", "0").split()[0])
                        speed2 = float(ship2.get("Speed", "0").split()[0])
                        if speed1 <= speed_threshold and speed2 <= speed_threshold:
                            paired_ships.append((ships[i], ships[j], distance))
                    else:
                        paired_ships.append((ships[i], ships[j], distance))

        self.save_paired_ships(paired_ships, data, directory)

    def is_valid_ship(self, ship):
        return ship.get("IMO", "").replace("'", "").isdigit()

    def calculate_rectangle_distance(self, lat1, lon1, size1, lat2, lon2, size2):
        """
        Calculates the minimal distance between two rectangles representing ships.
        :param lat1, lon1: center of the first ship
        :param size1: size of the first ship (length x width in meters)
        :param lat2, lon2: center of the second ship
        :param size2: size of the second ship (length x width in meters)
        :return: minimal distance between the two rectangles
        """
        def parse_size(size):
            size = size.replace(' m', '')
            parts = size.split(' x ')
            if len(parts) == 1:
                length = float(parts[0])
                width = 0
            else:
                length, width = map(float, parts)
            return length, width

        if size1 == '---' or size1 == '0 m':
            size1 = '0 x 0'
        if size2 == '---' or size2 == '0 m':
            size2 = '0 x 0'

        length1, width1 = parse_size(size1)
        length2, width2 = parse_size(size2)

        # Convert size from meters to degrees (approximation)
        lat1_offset = length1 / 111320  # 1 degree latitude is approx 111.32 km
        lon1_offset = width1 / (111320 * cos(radians(lat1)))

        lat2_offset = length2 / 111320
        lon2_offset = width2 / (111320 * cos(radians(lat2)))

        corners1 = [
            (lat1 + lat1_offset / 2, lon1 + lon1_offset / 2),
            (lat1 + lat1_offset / 2, lon1 - lon1_offset / 2),
            (lat1 - lat1_offset / 2, lon1 + lon1_offset / 2),
            (lat1 - lat1_offset / 2, lon1 - lon1_offset / 2),
        ]

        corners2 = [
            (lat2 + lat2_offset / 2, lon2 + lon2_offset / 2),
            (lat2 + lat2_offset / 2, lon2 - lon2_offset / 2),
            (lat2 - lat2_offset / 2, lon2 + lon2_offset / 2),
            (lat2 - lat2_offset / 2, lon2 - lon2_offset / 2),
        ]

        min_distance = float('inf')
        for corner1 in corners1:
            for corner2 in corners2:
                distance = self.calculate_distance(corner1[0], corner1[1], corner2[0], corner2[1])
                if distance < min_distance:
                    min_distance = distance

        return min_distance

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    def save_paired_ships(self, paired_ships, data, directory):
        paired_ships_data = []
        for pair in paired_ships:
            ship1_info = data[pair[0]]
            ship2_info = data[pair[1]]
            distance = pair[2]
            paired_ships_data.extend([
                {"Distance (m)": f"{distance:.2f}"},
                {"Ship 1": "-----------------------------"},
                ship1_info,
                {"Ship 2": "-----------------------------"},
                ship2_info,
                {},
                {}
            ])

        if paired_ships_data:
            df = pd.DataFrame(paired_ships_data)
            excel_file_name = os.path.join(directory, "paired_ships.xlsx")
            df.to_excel(excel_file_name, index=False)
            print(f"Paired ships saved as {excel_file_name}")
        else:
            print("No ships found within the specified thresholds.")

    def clean_directory(self, directory):
        json_file_path = os.path.join(directory, "vessels.json")
        with open(json_file_path, 'r', encoding='utf-8') as file:
            vessels_data = json.load(file)

        filtered_vessels_data = {}
        for vessel_id, vessel_info in vessels_data.items():
            imo = vessel_info.get("IMO", "")
            if imo and imo.replace("'","").isdigit():
                filtered_vessels_data[vessel_id] = vessel_info
            else:
                html_file_path = os.path.join(directory, f"{vessel_id}.html")
                if os.path.exists(html_file_path):
                    os.remove(html_file_path)

        with open(json_file_path, 'w', encoding='utf-8') as file:
            json.dump(filtered_vessels_data, file, indent=4)

        print(f"Cleaned directory '{directory}' and updated 'vessels.json'")

    def extract_most_visited_ports(self, soup):
        return self.extract_table_data(soup, 'ft-visitedports', ['port', 'arrivals'])

    def extract_last_trips(self, soup):
        return self.extract_table_data(soup, 'ft-lasttrips', ['origin', 'departure', 'destination', 'arrival', 'distance'])

    def extract_port_calls(self, soup):
        return self.extract_table_data(soup, 'ft-portcalls', ['port', 'arrival', 'departure', 'time_in_port'])

    def extract_table_data(self, soup, section_id, columns):
        section = soup.find('div', {'id': section_id})
        if not section:
            return []
        table = section.find('table', {'class': 'myst-table'})
        if not table:
            return []
        rows = table.find_all('tr')[1:]
        data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= len(columns):
                data.append({columns[i]: cols[i].text.strip() for i in range(len(columns))})
        return data

    def convert_json_to_excel(self, json_file_name):
        with open(json_file_name, 'r') as file:
            data = json.load(file)

        if not isinstance(data, dict):
            print("Invalid JSON structure.")
            return

        flattened_data = [{'ship_id': ship_id, **ship_info} for ship_id, ship_info in data.items()]
        df = pd.DataFrame(flattened_data)

        print("Available attributes:")
        for i, col in enumerate(df.columns):
            print(f"{i + 1}: {col}")

        exclude_indices = input("Enter the numbers of the attributes to exclude, separated by commas: ").split(',')
        exclude_indices = [int(index.strip()) - 1 for index in exclude_indices if index.strip().isdigit()]

        columns_to_include = [col for i, col in enumerate(df.columns) if i not in exclude_indices]
        df_filtered = df[columns_to_include]

        excel_file_name = json_file_name.replace(".json", ".xlsx")
        df_filtered.to_excel(excel_file_name, index=False)
        print(f"Excel file saved as {excel_file_name}")
    
    def create_map_html(self, directory, selected_area):
        shape = selected_area['shape']
        bounds = shape.bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
        
        if isinstance(shape, Point):
            folium.CircleMarker(
                location=[shape.y, shape.x],
                radius=5,
                popup='Selected Point',
                color='#3186cc',
                fill=True,
                fillColor='#3186cc'
            ).add_to(m)
        else:
            folium.GeoJson(shape).add_to(m)
        
        plugins.Fullscreen().add_to(m)
        m.fit_bounds(m.get_bounds())
        
        map_path = os.path.join(directory, 'selected_area_map.html')
        m.save(map_path)

    def save_geojson(self, directory, selected_area):
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": selected_area['shape'].__geo_interface__,
                "properties": {}
            }]
        }
        
        geojson_path = os.path.join(directory, 'selected_area.geojson')
        with open(geojson_path, 'w') as f:
            json.dump(geojson, f)
    
    def plot_area_interactive(self, center_lat, center_lon, inner_radius_km, outer_radius_km, directory):
        map = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenStreetMap')
        folium.Circle(
            radius=outer_radius_km * 1000,
            location=[center_lat, center_lon],
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.1,
            popup=f'Outer Radius: {outer_radius_km} km'
        ).add_to(map)

        if inner_radius_km > 0:
            folium.Circle(
                radius=inner_radius_km * 1000,
                location=[center_lat, center_lon],
                color='green',
                fill=True,
                fill_color='green',
                fill_opacity=0.2,
                popup=f'Inner Radius: {inner_radius_km} km'
            ).add_to(map)

        map_path = os.path.join(directory, 'map.html')
        map.save(map_path)
        webbrowser.open(map_path)

    def execute_all_tasks(self, directory, selected_area, distance_threshold=50, speed_threshold=None):
        ships = self.get_ships_in_area(selected_area)
        vessels = {}
        for ship_id in ships:
            ship_data = self.get_ship_data(ship_id, directory)
            if ship_data:
                vessels[ship_id] = ship_data
        json_file_path = os.path.join(directory, "vessels.json")
        with open(json_file_path, 'w') as file:
            json.dump(vessels, file, indent=4)
        self.convert_json_to_excel(json_file_path)
        self.pair_nearby_ships(directory, distance_threshold, speed_threshold)

def main():
    analyzer = ShipDataAnalyzer()
    def print_header():
        clear_screen()
        print(Fore.BLUE + Style.BRIGHT + "=" * 50)
        print("      Schiffsdaten-Analyse-Programm")
        print("=" * 50 + Style.RESET_ALL)
    def print_menu():
        print(Fore.GREEN + "\nWählen Sie eine Aktion aus:")
        print("1. Herunterladen und Speichern von Schiffsdaten")
        print("2. Konvertieren von JSON zu Excel")
        print("3. Paaren von nahegelegenen Schiffen")
        print("4. Verarbeiten von HTML-Dateien im Verzeichnis")
        print("5. Alle Aufgaben ausführen")
        print("6. Verzeichnis bereinigen")
        print("7. Beenden")
        print(Style.RESET_ALL)
    def user_choice():
        print_menu()
        return int(input(Fore.YELLOW + "Geben Sie Ihre Wahl ein (1-7): " + Style.RESET_ALL))

    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')
    while True:
        colorama.init()
        print_header()
        action = user_choice()
        
        if action == 1 or action == 5:
            print(Fore.CYAN + "\nÖffne die Karte zur Bereichsauswahl..." + Style.RESET_ALL)
            analyzer.open_html_page()
            print(Fore.CYAN + "Bitte wählen Sie einen Bereich auf der Karte aus und klicken Sie auf 'Bestätigen'." + Style.RESET_ALL)
            selected_area = analyzer.load_data()
            
            if action == 1:
                print(Fore.CYAN + "\nLade Schiffsdaten..." + Style.RESET_ALL)
                ships = analyzer.get_ships_in_area(selected_area)
                directory = analyzer.setup_directory(selected_area)
                vessels = {}
                for ship_id in ships:
                    ship_data = analyzer.get_ship_data(ship_id, directory)
                    if ship_data:
                        vessels[ship_id] = ship_data
                json_file_path = os.path.join(directory, "vessels.json")
                with open(json_file_path, 'w') as file:
                    json.dump(vessels, file, indent=4)
                print(Fore.GREEN + f"\nSchiffsdaten wurden in {json_file_path} gespeichert." + Style.RESET_ALL)
            elif action == 5:
                distance_threshold = float(input(Fore.YELLOW + "\nGeben Sie den Abstandsschwellenwert in Metern für die Gruppierung ein (Standard: 75): " + Style.RESET_ALL) or 75)
                speed_threshold = float(input(Fore.YELLOW + "Geben Sie den Geschwindigkeitsschwellenwert in Knoten für die Gruppierung ein (optional): " + Style.RESET_ALL) or 0)
                print(Fore.CYAN + "\nFühre alle Aufgaben aus..." + Style.RESET_ALL)
                directory = analyzer.setup_directory(selected_area)
                analyzer.execute_all_tasks(directory, selected_area, distance_threshold, speed_threshold)


        elif action == 2:
            directory = input(Fore.YELLOW + "\nGeben Sie das Verzeichnis mit der JSON-Datei ein: " + Style.RESET_ALL)
            analyzer.convert_json_to_excel(os.path.join(directory, "vessels.json"))
        elif action == 3:
            directory = input(Fore.YELLOW + "\nGeben Sie das Verzeichnis mit der JSON-Datei ein: " + Style.RESET_ALL)
            distance_threshold = float(input(Fore.YELLOW + f"Geben Sie den Abstandsschwellenwert in Metern für das Paaren ein (Standard: 75): " + Style.RESET_ALL) or 75)
            speed_threshold = float(input(Fore.YELLOW + "Geben Sie den Geschwindigkeitsschwellenwert in Knoten für das Paaren ein (optional): " + Style.RESET_ALL) or 0)
            analyzer.pair_nearby_ships(directory, distance_threshold, speed_threshold)
        elif action == 4:
            directory = input(Fore.YELLOW + "\nGeben Sie das Verzeichnis mit den HTML-Dateien ein: " + Style.RESET_ALL)
            analyzer.process_html_files_in_directory(directory)
        elif action == 6:
            directory = input(Fore.YELLOW + "\nGeben Sie das zu bereinigende Verzeichnis ein: " + Style.RESET_ALL)
            analyzer.clean_directory(directory)
        elif action == 7:
            print(Fore.GREEN + "\nProgramm wird beendet." + Style.RESET_ALL)
            break
        else:
            print(Fore.RED + "\nUngültige Auswahl. Bitte versuchen Sie es erneut." + Style.RESET_ALL)

        input(Fore.YELLOW + "\nDrücken Sie Enter, um fortzufahren..." + Style.RESET_ALL)

if __name__ == "__main__":
    main()
