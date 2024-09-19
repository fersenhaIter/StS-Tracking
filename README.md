# Ship Tracking & Analysis Tool

<img src="cover_.jpg" alt="Project Cover" align="right" style="width: 200px; border: 2px solid black; margin-left: 20px; float: right;"/>


## Overview

This tool is designed to assist in tracking and analyzing ship movements, particularly within a user-defined geographical area. It retrieves vessel data, processes the information, and provides valuable insights such as ship characteristics, nearby ships, and potential groupings. Originally designed to analyze data in the context of bypassing oil sanctions, the program now serves a broader purpose in maritime tracking and analysis.

The tool is built using Python, Folium for mapping, and various geospatial libraries, and is intended for use with publicly available ship tracking services like MyShipTracking.

## Features

- **Interactive Map for Area Selection**: Users can define a region of interest via a web-based map. The selected area is then saved as a GeoJSON file.
- **Vessel Data Retrieval**: Retrieves ship data (MMSI, location, type, etc.) for all vessels within the selected area.
- **Data Storage and Management**: Stores ship data as JSON, processes it into Excel format, and pairs nearby ships based on proximity and speed.
- **Ship Pairing**: Identifies and groups vessels that are near each other, based on a customizable distance threshold.
- **Automated HTML Processing**: Processes stored ship information and converts it into structured JSON and Excel reports.
- **Interactive Visualization**: Generates maps and plots selected areas or ships of interest.
  
## Requirements

- Python 3.7+
- Required packages (install with `pip`):
  - `folium`
  - `requests`
  - `beautifulsoup4`
  - `pandas`
  - `geopandas`
  - `colorama`
  - `shapely`

```bash
pip install folium requests beautifulsoup4 pandas geopandas colorama shapely
```

## Files

- **`program.py`**: Main script to perform ship data analysis and interaction with user-defined areas.
- **`index.html`**: Interactive map page for selecting geographic areas. Utilizes Leaflet.js for drawing areas.
- **`run_ship_tracking.sh`** and **`run_ship_tracking.bat`**: Scripts to execute the program on Linux/Mac or Windows.

## How to Use

1. **Select an Area**:
   - Run the program and an interactive map will open in your web browser.
   - Draw a shape (polygon, circle, or rectangle) to define the area of interest.
   - Confirm the selection to save the area as a GeoJSON file.

2. **Retrieve and Analyze Data**:
   - After selecting the area, the program will retrieve the vessels in the selected area using MyShipTracking's API.
   - The data will be saved in a new directory, organized by timestamp.
   
3. **Process Data**:
   - The program can process ship data stored as HTML files, converting them into structured JSON and Excel formats.
   - It also allows pairing ships based on proximity, storing results in a spreadsheet for further analysis.

4. **Advanced Tasks**:
   - Convert JSON to Excel for easy viewing and filtering.
   - Clean directories by removing incomplete or erroneous data files.
   - Use additional settings for pairing ships by proximity and speed.

## Example Usage

```bash
python program.py
```

The tool will prompt you to:
- Open the interactive map for area selection.
- Retrieve ship data from the defined region.
- Process data and export the results in multiple formats (JSON, Excel).

## Potential Applications

- **Sanctions Evasion Analysis**: Track suspicious vessel movements in regions known for bypassing oil sanctions.
- **Maritime Surveillance**: Monitor ship traffic in key areas for security or environmental research.
- **Shipping and Logistics**: Analyze vessel paths and optimize shipping routes.

## License

This project is licensed under the MIT License.

---

Feel free to adjust the wording or content to better suit your needs!
