# Meal Planner — User Guide

A comprehensive reference for using the Meal Planner web application.

---

## Table of Contents

1. [What Is Meal Planner?](#what-is-meal-planner)
2. [Getting Started](#getting-started)
3. [Features Overview](#features-overview)
4. [Pantry](#pantry)
5. [Recipes](#recipes)
6. [Meal Plan](#meal-plan)
7. [Shopping List](#shopping-list)
8. [Stores](#stores)
9. [Settings](#settings)
10. [Demo Mode](#demo-mode)
11. [Dictionary of Terms](#dictionary-of-terms)

---

## What Is Meal Planner?

Meal Planner is a personal, self-hosted web application for managing your household food inventory, planning weekly meals, generating shopping lists, and building a recipe library. It is designed to run on your local network or a private server, accessible from any browser.

**Core workflow:**
1. Import your pantry inventory (or add items manually).
2. Build a recipe library (manually, by pasting text, from a URL, or with AI assistance).
3. Assign recipes to days and meal slots on a weekly calendar.
4. Generate a shopping list that automatically subtracts what you already have in your pantry.

All data is stored in a local SQLite database file. Nothing is sent to external services except for optional AI features, which use the Anthropic Claude API.

---

## Getting Started

### Logging In

The application is protected by a single shared password. Navigate to the application URL and enter your password on the login screen. Once logged in, your session persists in a signed browser cookie. You will be redirected to `/pantry` after a successful login.

**Do:**
- Use a strong, unique password set via the `APP_PASSWORD` environment variable before first use.
- Access the app from any device on your network using the server's IP address.

**Do not:**
- Share your login URL with people you do not want to have full read/write access — there is one password and one access level.
- Expose the app to the public internet without additional security (e.g., VPN, firewall rules).

### Navigation

The top navigation bar links to all main sections: Pantry, Recipes, Meal Plan, Shopping, Stores, and Settings.

---

## Features Overview

| Section      | What it does                                                        |
|--------------|---------------------------------------------------------------------|
| Pantry       | Track food inventory: quantities, expiry dates, locations, stores   |
| Recipes      | Store and manage recipes with ingredients and instructions          |
| Meal Plan    | Assign recipes to specific days and meal slots on a weekly calendar |
| Shopping     | Generate a shopping list from your meal plan, minus pantry stock    |
| Stores       | Manage the list of stores where you shop                            |
| Settings     | Configure your Claude API key for AI features                       |

---

## Pantry

The Pantry tab is your food inventory. It tracks everything you currently have at home, including quantity, expiry dates, storage location, and which store you normally buy each item from.

### Viewing Your Pantry

The pantry displays as a table with columns: Name, Brand, Category, Location, Quantity, Unit, Best By (expiry date), and Store.

- **Red rows**: the item's best-by date has passed (expired).
- **Orange rows**: the item expires within the next 7 days.

Use the **Location** and **Category** filter dropdowns at the top to narrow the list. Selecting a filter immediately reloads only the matching rows.

### Adding Items Manually

Click **Add Item** to open the item form. Fill in:

- **Name** (required): the item's name as you want it to appear and match against recipes.
- **Brand**: optional brand name.
- **Category**: e.g., Dairy, Produce, Canned Goods. Helps with filtering.
- **Location**: where it is stored, e.g., Fridge, Freezer, Pantry. Helps with filtering.
- **Quantity** and **Unit**: how much you have and in what unit (g, ml, cups, etc.).
- **Best By**: expiry date. Leave blank if not applicable.
- **Preferred Store**: where you normally buy this item. Used when generating shopping lists to group items by store.

**Do:**
- Use consistent spelling for item names. The shopping list uses case-insensitive name matching to subtract pantry stock from your shopping list — `Chicken Breast` and `chicken breast` will match, but `Chicken` and `Chicken Breast` will not.
- Keep units consistent between your pantry and recipe ingredients (e.g., both in grams, or both in cups) for accurate quantity subtraction.

**Do not:**
- Add the same item twice with different spellings — the duplicate will not match your recipes correctly.

### Importing from PantryChecker CSV

If you use the PantryChecker app to scan barcodes, you can export a CSV from PantryChecker and import it here.

Click **Import CSV**, select your exported CSV file, and click Upload. The importer will:
1. Match items by barcode if available.
2. Fall back to matching by name + brand if no barcode.
3. Update existing items (quantity, expiry, etc.).
4. Insert new items that do not match anything existing.
5. Auto-create any stores referenced in the CSV that do not yet exist in your Stores list.

**Do:**
- Import regularly to keep your pantry up to date.
- Correct item names in PantryChecker (or here after import) if they do not match what you use in recipes.

**Do not:**
- Manually edit items and then re-import without checking — the importer will overwrite manual changes if the barcode or name+brand matches.

### Editing and Deleting Items

Click **Edit** on any row to open the same form pre-filled with that item's data. Click **Delete** to permanently remove it.

---

## Recipes

The Recipes tab is your recipe library. The screen is split: a searchable list on the left, and the selected recipe's full details on the right.

### Browsing and Searching

Type in the search box to filter recipes by name, description, or tags. The list updates as you type.

Click any recipe in the list to view its full details: name, description, serving size, prep/cook time, tags, a link to the original source (if any), ingredients, and instructions.

### Adding a Recipe Manually

Click **Add Recipe** to open the recipe form. Fill in:

- **Name** (required): the recipe name.
- **Description**: a short summary.
- **Servings**: how many servings the recipe makes.
- **Prep Time / Cook Time**: in minutes.
- **Tags**: comma-separated labels (e.g., `chicken, quick, weeknight`).
- **Source URL**: optional link to the original recipe.
- **Ingredients**: click **Add Ingredient** to add rows. Each row has Name, Quantity, Unit, and optionally a shopping-specific Name, Quantity, and Unit (for when the shopping name or pack size differs from the recipe amount).
- **Instructions**: free-form text with the cooking steps.

**Do:**
- Use the same ingredient names you use in your pantry for accurate shopping list subtraction.
- Fill in servings accurately — the shopping list multiplies ingredient quantities by the number of servings you assign when planning meals.

**Do not:**
- Leave ingredient names blank — they will appear on your shopping list with no label.
- Use abbreviations inconsistently (e.g., `tsp` in one recipe, `teaspoon` in another) as these count as different units and will not aggregate on the shopping list.

### AI: Paste Recipe Text

Click **Paste Text** to extract a recipe from copied text. Paste the full text of a recipe (from a website, cookbook photo, email, etc.) into the text box and click Parse. Claude AI reads the text and fills in the recipe form with name, ingredients, instructions, and other fields.

Review the pre-filled form before saving — AI extraction is accurate but may need minor corrections.

**Do:**
- Paste as much context as possible (title, ingredient list, instructions).
- Review and correct the extracted ingredients, especially units and quantities.

**Do not:**
- Paste a URL here — use **From URL** instead.
- Save without reviewing. Check that ingredient names match how you use them elsewhere.

### AI: From URL

Click **From URL** and enter a web address to a recipe page. The app fetches the page, strips the HTML, and sends the text to Claude AI to extract the recipe.

**Do:**
- Use direct recipe page URLs (not search results or category pages).
- Review the extracted recipe before saving.

**Do not:**
- Expect this to work on every website — some sites use heavy JavaScript rendering that prevents clean text extraction. If the result looks wrong or empty, try Paste Text instead by copying the recipe text manually.
- Use URLs that require a login to view.

### AI: Generate Recipe

Click **AI Generate** to have Claude create a new recipe based on what you have in your pantry. Optionally enter preferences (e.g., "vegetarian", "quick weeknight meal", "uses up the spinach") before generating.

Claude uses your current pantry inventory as context to suggest a recipe that uses ingredients you have on hand.

**Do:**
- Add preferences to guide the result (cuisine type, dietary restrictions, time constraints).
- Review the generated recipe — it is a starting point, not a final product.

**Do not:**
- Expect perfect accuracy on quantities and cooking times — AI-generated recipes may need adjustments.
- Use this feature without a Claude API key configured in Settings.

### AI: Modify Recipe

With a recipe selected and visible in the detail panel, click **Modify with AI**. Enter an instruction such as "make it vegetarian", "double the garlic", or "adapt for 2 servings". Claude will return a modified version of the recipe for you to review and save.

**Do:**
- Be specific in your instruction ("replace chicken with tofu" is better than "make it different").
- Compare the modified result to the original before saving.

**Do not:**
- Use this as a replace-in-place operation without reviewing — the AI may change more than you intended.

### Editing and Deleting Recipes

With a recipe selected, click **Edit** to open the full form pre-filled for that recipe. Editing replaces all ingredients (existing ingredient records are deleted and re-inserted).

Click **Delete** to permanently remove the recipe. If the recipe is assigned to any meal plan days, those assignments will become blank (the recipe reference is cleared, not the slot).

---

## Meal Plan

The Meal Plan tab displays a weekly calendar with 4 meal slots per day: Breakfast, Lunch, Dinner, and Snack.

### Navigating Weeks

Use **Prev**, **Next**, and **Today** buttons to move between weeks. The week always starts on Monday. The current day is highlighted.

### Assigning a Meal

Click any cell in the grid to open the meal picker. From the picker, you can:
- Select a recipe from a searchable dropdown.
- Set the number of servings.
- Add optional notes for that day/slot.
- Clear the current assignment.

Click **Save** to assign the recipe to that slot, or **Clear** to remove an existing assignment.

**Do:**
- Set servings accurately — the shopping list uses this number to scale ingredient quantities.
- Use the notes field for reminders like "defrost night before" or "halve recipe".

**Do not:**
- Assign a recipe to a slot and then delete that recipe — the slot will become empty. Re-assign if needed.

### AI: Suggest Week

Click **AI Suggest Week** to have Claude propose a full week of meals. Optionally enter preferences (e.g., "light lunches", "no fish", "use pantry items"). Claude returns a table of suggestions you can review before applying.

The suggestion table shows each proposed day/slot/meal. Click **Apply Suggestions** to write them all to the meal plan at once. Only meals that match an existing recipe name in your library are applied — unmatched suggestions are ignored.

**Do:**
- Review suggestions before applying — you can cancel if the proposals do not look right.
- Add preferences to guide the result toward your household's tastes.

**Do not:**
- Expect all suggestions to match your recipe library by name — Claude proposes recipe names, and only exact matches (case-insensitive) are applied. Add the suggested recipe to your library first if it is not there yet.

---

## Shopping List

The Shopping List tab generates a list of ingredients you need to buy based on the recipes in your meal plan.

### Generating a List

1. Set the **Start Date** and **End Date** to define the date range.
2. Check or uncheck **Subtract pantry items** (checked by default).
3. Click **Generate**.

The app:
1. Collects all recipes assigned in the date range.
2. Multiplies each ingredient's quantity by the servings set in the meal plan.
3. Aggregates identical ingredients (matched by name and unit).
4. If pantry subtraction is on: subtracts current pantry stock and omits items you already have enough of.
5. Groups the remaining items by preferred store.

The result displays as a checklist grouped by store. Check off items as you shop.

### "This Week" Shortcut

Click the **This Week** button to automatically set the date range to the current Monday–Sunday.

### Exporting the List

Click **Export as Text** to download the shopping list as a plain-text `.txt` file with checkboxes. The file can be shared or copied into a notes app.

**Do:**
- Keep pantry quantities up to date before generating — this is what makes the subtraction accurate.
- Use consistent ingredient names between recipes and pantry items.

**Do not:**
- Generate a list for a date range with no meal plan entries — the result will be empty.
- Rely on unit conversion — the app does not convert units. If a recipe lists `500g flour` and your pantry has `1 cup flour`, they will not subtract from each other.

---

## Stores

The Stores tab manages the list of shops where you buy groceries. Stores are used throughout the app to group shopping list items and track where you prefer to buy each pantry item.

### Adding and Editing Stores

Click **Add Store** to create a new store entry with a name. Click **Edit** or **Delete** on any existing store.

**Do:**
- Create stores before importing pantry data if your CSV references store names — unrecognised stores in a CSV import are auto-created, but using pre-existing entries avoids duplicates.
- Use the full, recognisable name of the store (e.g., "Whole Foods" not "WF").

**Do not:**
- Delete a store that is assigned to pantry items or set as a preferred store. The store reference on those items will become blank.

---

## Settings

The Settings tab stores your Claude API key, which is required for all AI features.

### Configuring the Claude API Key

1. Go to [console.anthropic.com](https://console.anthropic.com) and generate an API key.
2. In Settings, paste the key into the **Claude API Key** field.
3. Click **Save**.

The key is stored in the application database (not in a config file). It is sent to Anthropic's API only when you use an AI feature.

**Do:**
- Keep your API key private. Anyone with access to the app can use AI features (and incur API charges) once a key is saved.
- Monitor your Anthropic API usage if you use AI features frequently.

**Do not:**
- Share screenshots of the Settings page with the key visible.

---

## Demo Mode

The application includes a read-only demo mode accessible at `/demo/pantry` (and other `/demo/*` paths) without requiring a login.

Demo mode uses a separate database pre-seeded with example data: sample recipes, a pantry inventory, and a week of meal plan entries. No changes made in demo mode affect the real database.

All write actions (Add, Edit, Delete, Import) are hidden in demo mode.

**Use demo mode to:**
- Show the application to someone without giving them your login password.
- Explore the app layout and features on first setup before adding your own data.

---

## Dictionary of Terms

**Best By / Expiry Date**
The date after which a pantry item should no longer be used. Items past this date are highlighted red; items within 7 days of this date are highlighted orange.

**Category**
A label on a pantry item for grouping (e.g., Dairy, Produce, Canned Goods). Used for filtering the pantry view.

**Claude API Key**
An authentication key from Anthropic (format: `sk-ant-...`) required to use AI features. Configured in Settings.

**Demo Mode**
A read-only view of the application at `/demo/*` using a separate pre-seeded database. No login required. No changes affect the real database.

**Ingredient Matching**
How the shopping list engine compares ingredient names in recipes against pantry item names. Matching is case-insensitive and whitespace-trimmed. Names must otherwise be identical — there is no fuzzy or synonym matching.

**Location**
Where a pantry item is physically stored (e.g., Fridge, Freezer, Pantry, Cupboard). Used for filtering the pantry view.

**Meal Slot**
One of four named time-of-day positions per day in the meal plan: Breakfast, Lunch, Dinner, Snack.

**Pantry**
The application's food inventory: all items you currently have at home with their quantities, expiry dates, locations, and preferred stores.

**PantryChecker**
A third-party barcode-scanning mobile app used to track home food inventory. Its CSV export format is supported for import into the Pantry tab.

**Preferred Store**
The store associated with a pantry item — where you normally buy that item. Used by the shopping list to group items under the correct store.

**Recipe**
A named dish with ingredients (name, quantity, unit), instructions, metadata (servings, prep/cook time, tags), and an optional source URL.

**Recipe Ingredient**
One line in a recipe's ingredient list: a name, quantity, and unit. Optionally has separate shopping-specific fields (shopping name, shopping quantity, shopping unit) for when the item is purchased in different units or under a different name than used in cooking.

**Serving / Servings**
How many portions a recipe makes. When assigning a recipe to a meal plan slot, you set a number of servings, and the shopping list multiplies all ingredient quantities by that number.

**Shopping List**
An auto-generated list of ingredients needed for a date range of meal plan entries, with pantry stock optionally subtracted and items grouped by preferred store.

**Staple**
An item you always want on hand (e.g., salt, olive oil). Staples with `need_to_buy = 0` are excluded from shopping lists. Staples with `need_to_buy = 1` are appended to the list. (Note: staple management is an internal database feature and does not currently have a UI.)

**Store**
A named shop or retailer (e.g., Tesco, Costco, Local Farm Shop). Stores are managed in the Stores tab and referenced by pantry items and shopping list groupings.

**Tags**
Comma-separated labels on a recipe (e.g., `vegetarian, quick, pasta`). Searchable from the Recipes tab.

**Unit**
The measurement unit for an ingredient quantity (e.g., g, kg, ml, cup, tbsp, tsp, whole). Units must match between recipe ingredients and pantry items for shopping list subtraction to work correctly.
