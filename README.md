# 🍷 Wine & Food Pairer (Offline Edition)

A desktop application that uses a local CSV database to provide instant wine and food pairings. It works entirely offline and allows for custom data management via Excel/CSV.

## 🚀 Features
* **Bidirectional Search:** Find food for a specific wine OR wine for a specific food.
* **Fuzzy Matching:** Handles typos and capitalization errors automatically.
* **Customizable Database:** Edit the `wine_food_pairings.csv` file to add your own menu items.
* **Zero Latency:** Instant results with no internet connection required.

## 📋 Prerequisites
* Python 3.x installed.
* The `pandas` library.

## 🛠️ Installation & Setup

1.  **Install Dependencies:**
    ```bash
    pip install pandas
    ```

2.  **Prepare the Database:**
    Ensure a file named `wine_food_pairings.csv` is in the same folder.
    *Format:*
    ```csv
    wine,food
    Merlot,Roast Chicken
    Chianti,Pizza
    ...
    ```

3.  **Run the App:**
    ```bash
    python app.py
    ```

## 💡 Pro Tip
To turn this into a standalone `.exe` file that runs without Python:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed app.py
