import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import difflib
import os

# --- 1. Load Database from CSV ---
def load_data():
    csv_file = "wine_food_pairings.csv"
    
    if not os.path.exists(csv_file):
        messagebox.showerror("Error", f"Could not find {csv_file}!")
        return {}

    try:
        df = pd.read_csv(csv_file)
        
        # Normalize wine names to lowercase for the dictionary keys (lookup)
        # But keep the original 'food' casing for display
        df['wine_key'] = df['wine'].str.lower().str.strip()
        
        # Create the dictionary: { "merlot": ["Roast Chicken", "Beef Stew"] }
        data_dict = df.groupby("wine_key")["food"].apply(list).to_dict()
        return data_dict

    except Exception as e:
        messagebox.showerror("Error", f"Failed to read CSV:\n{e}")
        return {}

# Load data on startup
data = load_data()

# --- 2. The Smart Logic ---
def get_pairing(user_input):
    if not data:
        return "⚠️ Database is empty or missing."

    clean_input = user_input.lower().strip()
    
    # A. Direct Match Check (Wine -> Food)
    if clean_input in data:
        return format_wine_result(clean_input)

    # B. Reverse Search (Food -> Wine)
    found_wines = []
    for wine_key, foods in data.items():
        # Check if input is inside any food string (e.g. "chicken" in "Roast Chicken")
        if any(clean_input in food.lower() for food in foods):
            found_wines.append(wine_key.title())
    
    if found_wines:
        return f"🍽️ '{user_input.title()}' goes best with:\n• " + "\n• ".join(found_wines)

    # C. Fuzzy Match (Did you mean?)
    all_wines = list(data.keys())
    # Flatten all foods into one list for searching
    all_foods = [food for sublist in data.values() for food in sublist]
    all_keywords = all_wines + all_foods
    
    # Check for close matches (cutoff=0.6)
    matches = difflib.get_close_matches(clean_input, [str(k).lower() for k in all_keywords], n=1, cutoff=0.6)
    
    if matches:
        suggestion = matches[0]
        return f"❓ Did you mean '{suggestion.title()}'?\n\n" + get_pairing(suggestion)

    return "❌ No pairing found.\nTry a broader term like 'Chicken', 'Cheese', or 'Red'."

def format_wine_result(wine_key):
    # Capitalize the wine key for display
    display_name = wine_key.title()
    foods = data[wine_key]
    return f"🍷 {display_name} pairs well with:\n• " + "\n• ".join(foods)

def on_search(event=None):
    user_input = entry.get()
    if not user_input:
        return
    
    result = get_pairing(user_input)
    result_label.config(text=result)

# --- 3. The GUI ---
root = tk.Tk()
root.title("CSV Sommelier 🍷")
root.geometry("450x500")
root.configure(bg="#f0f0f0")

# Styles & Header
style = ttk.Style()
style.theme_use('clam')

header_frame = tk.Frame(root, bg="#722F37", height=80)
header_frame.pack(fill="x")
tk.Label(header_frame, text="Wine & Food Pairer", font=("Segoe UI", 18, "bold"), bg="#722F37", fg="white").pack(pady=20)

# Input
input_frame = tk.Frame(root, bg="#f0f0f0")
input_frame.pack(pady=20)

tk.Label(input_frame, text="Enter Wine or Food:", bg="#f0f0f0").pack(anchor="w", padx=5)
entry = ttk.Entry(input_frame, font=("Segoe UI", 12), width=30)
entry.pack(pady=5, ipady=3)
entry.bind('<Return>', on_search)

tk.Button(input_frame, text="Find Pairing", command=on_search, bg="#722F37", fg="white", 
          font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=5).pack(pady=10)

# Results
result_frame = tk.Frame(root, bg="white", bd=1, relief="solid")
result_frame.pack(pady=10, padx=40, fill="both", expand=True)

result_label = tk.Label(result_frame, text="Ready to search...", font=("Segoe UI", 11), 
                        bg="white", justify="left", wraplength=350)
result_label.pack(pady=20, padx=20)

root.mainloop()