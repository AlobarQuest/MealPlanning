# Meal Planner

A cross-platform desktop application for managing food inventory, planning meals, generating shopping lists, and leveraging AI (Claude) for recipe management. All data is stored locally in SQLite.

## Features

- **Pantry Management**: Import from PantryChecker CSV, track inventory by location (Pantry/Fridge/Freezer), expiry date warnings
- **Recipe Library**: Store recipes with ingredients and instructions
- **AI-Powered Recipe Tools**:
  - Generate recipes from your pantry contents
  - Parse recipes from pasted text or URLs
  - Suggest full week meal plans
  - Modify existing recipes
- **Meal Planning**: Weekly calendar view to plan meals
- **Smart Shopping Lists**: Auto-generate shopping lists from meal plans, subtract pantry stock, group by store

## Requirements

- Python 3.10+
- A Claude API key from [Anthropic](https://console.anthropic.com/)

## Installation

1. Clone or download this repository
2. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Application

```bash
# From the project root directory
python main.py
```

On first run, the SQLite database will be created at `~/.meal_planner/meal_planner.db`.

## Getting Started

### 1. Add Your API Key
- Go to **File → Settings**
- Paste your Claude API key (starts with `sk-ant-...`)
- Click OK

Your API key is stored only in the local database and never transmitted anywhere except to Anthropic's API.

### 2. Import Your Pantry
- Go to **File → Import Pantry CSV...**
- Select your `inventory.csv` from PantryChecker
- The app will import all items, creating or updating them as needed

### 3. Add Recipes

You have several options:

**Manual Entry**
- Go to the **Recipes** tab
- Click **Add** and fill in the form

**Paste Recipe Text**
- Click **Paste**
- Paste any recipe text (from a website, document, etc.)
- Claude will extract and structure it
- Preview and save

**Import from URL**
- Click **From URL**
- Enter a recipe URL
- Claude will fetch and parse the recipe

**AI Generate**
- Click **AI Generate**
- Claude will create a recipe using your current pantry items
- Optionally add preferences (e.g. "vegetarian, quick, under 30 min")

### 4. Plan Your Meals

- Go to the **Meal Plan** tab
- Use the navigation buttons to select a week
- Click any cell (day + meal slot) to assign a recipe
- Select the recipe and servings

**AI Suggest Week**
- Click **AI Suggest Week**
- Claude will fill in the entire week based on your pantry and saved recipes

### 5. Generate Shopping List

- Go to the **Shopping List** tab
- Select date range (or click **This Week**)
- Click **Generate List**
- Items are grouped by store and show what you need to buy (subtracting pantry stock)
- Click **Copy to Clipboard** to export

## Project Structure

```
meal_planner/
├── main.py                  # Application entry point
├── PLAN.md                  # Full technical plan
├── README.md                # This file
├── requirements.txt         # Python dependencies
├── inventory.csv            # Your PantryChecker export
└── meal_planner/
    ├── config.py            # Settings management
    ├── db/
    │   ├── database.py      # Database schema and connection
    │   └── models.py        # Data models
    ├── core/
    │   ├── pantry.py        # Pantry logic
    │   ├── recipes.py       # Recipe CRUD
    │   ├── meal_plan.py     # Meal planning logic
    │   ├── shopping_list.py # Shopping list generation
    │   └── ai_assistant.py  # Claude AI integration
    └── gui/
        ├── main_window.py   # Main window and menu
        ├── pantry_tab.py    # Pantry UI
        ├── recipes_tab.py   # Recipes UI
        ├── meal_plan_tab.py # Meal planner UI
        └── shopping_tab.py  # Shopping list UI
```

## Tips

- **Pantry Location Filter**: Use the dropdowns in the Pantry tab to filter by location or category
- **Expiry Warnings**: Items expiring soon show in orange, expired items in red
- **Store Assignment**: Assign a preferred store to each pantry item for better shopping list grouping
- **Recipe Tags**: Use comma-separated tags (e.g. "chicken,quick,dinner") to organize recipes
- **Meal Servings**: When assigning a meal, adjust the servings multiplier for large gatherings

## Troubleshooting

**"Claude API key not set" error**
- Go to File → Settings and add your API key

**CSV import fails**
- Make sure the CSV file matches the PantryChecker format
- Check that required columns (Name, Quantity) are present

**AI features not working**
- Verify your API key is correct
- Check your internet connection
- Ensure you have API credits available

**Can't see the GUI on Linux/WSL**
- You need a working X server or Wayland session
- For WSL, install an X server like VcXsrv or use WSLg

## License

This project is provided as-is for personal use.

## Credits

- Built with [PySide6](https://www.qt.io/qt-for-python) (Qt for Python)
- AI features powered by [Claude](https://www.anthropic.com/claude) via the Anthropic API
- CSV import compatible with [PantryChecker](https://www.pantrychecker.com/)
