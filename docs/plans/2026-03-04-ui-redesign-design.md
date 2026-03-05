# UI Redesign — Design Document

**Date:** 2026-03-04
**Approach:** Full template + CSS redesign (Approach B)

---

## Goal

Modernise the Meal Planner web UI to a clean, Notion/Linear-style aesthetic that works equally well on desktop and mobile. Fix the narrow content problem, add recipe photo support, and improve visual hierarchy throughout.

---

## 1. Layout & Navigation

### Top Bar
- Full width, ~56px tall, white background, subtle bottom border/shadow
- Left: app name "Meal Planner" (weight 600)
- Right: Help link, Sign Out button

### Left Sidebar (desktop)
- 220px wide, white, fixed below the top bar, right border divider
- Nav items: Pantry, Recipes, Meal Plan, Shopping, Stores, Settings
- Each item: small icon + label
- Active state: filled blue-tinted pill (`#eff6ff` background, `#2563eb` text/icon)
- Inactive: muted grey; hover darkens slightly
- Smooth transition on hover/active

### Content Area
- Fills all space to the right of the sidebar
- No artificial narrow max-width — content uses the full available width

### Mobile (< 768px)
- Sidebar hidden entirely
- Bottom tab bar with 5 main tabs: Pantry, Recipes, Meal Plan, Shopping, Stores
- Settings + Help accessible from top bar (gear icon / help icon)
- Top bar remains at the top

---

## 2. Design System

### Colour Palette (CSS custom properties)
```css
--color-bg:          #f8fafc   /* page background */
--color-surface:     #ffffff   /* cards, sidebar, top bar */
--color-border:      #e2e8f0   /* dividers, input borders */
--color-text:        #0f172a   /* primary text */
--color-text-muted:  #64748b   /* secondary text, placeholders */
--color-accent:      #2563eb   /* buttons, links, active nav */
--color-accent-subtle: #eff6ff /* hover backgrounds, active nav fill */
--color-danger:      #dc2626   /* delete actions */
```

### Typography
- Font family: `system-ui, -apple-system, sans-serif` (unchanged)
- Base body size: 15px (up from 14px)
- Page headings: 18–20px, weight 600
- Section labels / table headers: 11–12px, weight 600, uppercase, letter-spacing 0.5px

### Spacing
- 4px base grid: common values 4, 8, 12, 16, 24, 32px
- Applied consistently to cards, form fields, gaps

### Surfaces & Depth
- Cards/panels: `box-shadow: 0 1px 3px rgba(0,0,0,.06)`
- Modals/dialogs: `box-shadow: 0 8px 32px rgba(0,0,0,.16)`

### Border Radius
- Cards and panels: 8px
- Buttons and inputs: 6px
- Tags/badges: 4px

---

## 3. Recipes Section

### List Panel
- Width: 300px (up from 280px)
- Each list item shows:
  - Recipe name (bold)
  - Tags as small coloured pills
  - 40×40px rounded thumbnail photo (if available)
- Search bar full width above the list
- Action buttons collapsed into a single **+ Add** button with a dropdown menu (Add Manually, Paste Text, From URL, AI Generate)

### Recipe Detail Panel
Three-zone layout:

```
┌─────────────────────────┬──────────────────────────┐
│  Ingredients            │  Photo                   │
│  (top-left)             │  (top-right)             │
├─────────────────────────┴──────────────────────────┤
│  Instructions (full width)                         │
└────────────────────────────────────────────────────┘
```

- **Header strip** above the two-column zone: recipe name, description, metadata (servings, prep time, cook time, tags, source link), Edit / Delete / Modify with AI buttons (right-aligned)
- **Top-left:** ingredient list
- **Top-right:** photo (or placeholder with dashed border + camera icon; clicking opens upload)
- **Below:** instructions with generous line height and padding
- **Mobile:** photo stacks above ingredients; single-column

### No-Photo Placeholder
- Dashed border, light grey background, centred camera icon
- Clicking it triggers the edit dialog with focus on the photo field

### Mobile Recipe Navigation
- List panel fills screen; selecting a recipe shows full-screen detail
- Back button (← Recipes) returns to the list

---

## 4. Photo Support

### Storage
- Photos stored in `app/static/uploads/recipes/`
- Directory created automatically on startup if it doesn't exist
- Filename: `{recipe_id}.jpg` — re-uploading replaces the existing file
- Served as static files via FastAPI's `StaticFiles` mount

### Upload
- File input in the add/edit recipe dialog
- Accepts JPG and PNG; server converts/saves as JPEG
- New field `photo_path` added to the `recipes` table (nullable `TEXT`)

### Auto-Fetch on URL Import
- After fetching and parsing a recipe URL, attempt to extract `og:image` meta tag
- Download the image and save it using the new recipe's ID
- Silent failure: if fetch fails for any reason, recipe saves without a photo

### Database Change
- `ALTER TABLE recipes ADD COLUMN photo_path TEXT` (migration-safe: added via `try/except` in `init_db`)

---

## 5. Remaining Tabs (Polish Only)

### Pantry
- Inherits new design system: row height, spacing, typography
- Expired/expiring row colours softened to match lighter palette
- Filter toolbar cleaned up — inline row, more breathing room above table

### Meal Plan
- Grid cells get more padding
- Today's column gets a subtle blue dot/underline on the day header
- Week navigation buttons use the updated button styles

### Shopping List
- Store group headers: light grey band instead of uppercase-only label
- Checkbox alignment tidied
- Generate/export toolbar matches pantry filter style

### Stores & Settings
- Inherit improved form and card styles only; no structural changes

---

## 6. Files Affected

| File | Change |
|---|---|
| `app/static/style.css` | Full rewrite |
| `app/templates/base.html` | New nav structure (top bar + sidebar) |
| `app/templates/recipes.html` | Updated split-pane, new detail layout |
| `app/templates/partials/recipe_list.html` | Thumbnails + tag pills |
| `app/templates/partials/recipe_detail.html` | Three-zone layout |
| `app/templates/partials/recipe_dialog.html` | Add photo upload field |
| `app/templates/pantry.html` | Minor polish |
| `app/templates/meal_plan.html` | Minor polish |
| `app/templates/shopping.html` | Minor polish |
| `app/routers/recipes.py` | Photo upload handling, og:image fetch |
| `meal_planner/db/database.py` | Add `photo_path` column migration |
| `meal_planner/db/models.py` | Add `photo_path` field to `Recipe` dataclass |
| `meal_planner/core/ai_assistant.py` | Extract og:image in `parse_recipe_url` |
| `app/main.py` | Mount uploads directory as static |
