# Staples Redesign, Bulk Delete & Receipt Pricing — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign staples as a standalone persistent list with have/need toggles, add bulk delete to pantry, and add receipt photo scanning for price extraction into a dedicated known_prices table.

**Architecture:** New `staples` and `known_prices` tables independent of pantry. Staples are managed via a dialog from the Pantry tab and can be added from recipe ingredients. Shopping list generation merges staples needing purchase with recipe-derived items. Receipt scanning uses Claude's vision API to extract prices, reviewed by user before saving. Price resolution in shopping list checks known_prices first.

**Tech Stack:** Python 3.10+, SQLite, PySide6, Anthropic SDK (Claude vision API for receipts)

---

### Task 1: Create `staples` table, model, and core CRUD

**Files:**
- Modify: `meal_planner/db/database.py:41-102` (add table to schema), `meal_planner/db/database.py:113-127` (migration)
- Modify: `meal_planner/db/models.py` (add Staple dataclass)
- Create: `meal_planner/core/staples.py`

**Step 1: Add `staples` table to schema**

In `meal_planner/db/database.py`, add this CREATE TABLE inside the `executescript` block (after the `settings` table, before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS staples (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    category           TEXT,
    preferred_store_id INTEGER REFERENCES stores(id),
    need_to_buy        INTEGER DEFAULT 0
);
```

**Step 2: Add `Staple` dataclass to models**

In `meal_planner/db/models.py`, add after the `MealPlanEntry` dataclass:

```python
@dataclass
class Staple:
    """A staple item the user normally keeps on hand (salt, pepper, oil, etc.).

    Independent of pantry — persists even when pantry items are consumed.
    When need_to_buy is True, the item appears on shopping lists.
    """
    id: Optional[int]
    name: str
    category: Optional[str] = None
    preferred_store_id: Optional[int] = None
    need_to_buy: bool = False
```

**Step 3: Create `meal_planner/core/staples.py`**

```python
"""Staples management — CRUD for persistent always-on-hand items.

Staples are independent of pantry inventory. Each staple has a need_to_buy
toggle; items marked as needed appear on shopping lists.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import Staple


def get_all() -> list[Staple]:
    """Return all staples sorted by name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM staples ORDER BY name").fetchall()
        return [Staple(**dict(row)) for row in rows]
    finally:
        conn.close()


def get(staple_id: int) -> Optional[Staple]:
    """Return a single staple by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM staples WHERE id = ?", (staple_id,)).fetchone()
        return Staple(**dict(row)) if row else None
    finally:
        conn.close()


def get_by_name(name: str) -> Optional[Staple]:
    """Return a staple by exact name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM staples WHERE LOWER(name) = LOWER(?)", (name.strip(),)
        ).fetchone()
        return Staple(**dict(row)) if row else None
    finally:
        conn.close()


def add(staple: Staple) -> int:
    """Insert a new staple. Return the new ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO staples (name, category, preferred_store_id, need_to_buy)
               VALUES (?, ?, ?, ?)""",
            (staple.name, staple.category, staple.preferred_store_id,
             int(staple.need_to_buy)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update(staple: Staple) -> None:
    """Update an existing staple."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE staples SET name=?, category=?, preferred_store_id=?,
               need_to_buy=? WHERE id=?""",
            (staple.name, staple.category, staple.preferred_store_id,
             int(staple.need_to_buy), staple.id),
        )
        conn.commit()
    finally:
        conn.close()


def delete(staple_id: int) -> None:
    """Delete a staple by ID."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM staples WHERE id = ?", (staple_id,))
        conn.commit()
    finally:
        conn.close()


def set_need_to_buy(staple_id: int, need: bool) -> None:
    """Toggle the need_to_buy flag for a staple."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE staples SET need_to_buy = ? WHERE id = ?",
            (int(need), staple_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_needed() -> list[Staple]:
    """Return all staples where need_to_buy is True."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM staples WHERE need_to_buy = 1 ORDER BY name"
        ).fetchall()
        return [Staple(**dict(row)) for row in rows]
    finally:
        conn.close()
```

**Step 4: Verify**

Run: `python3 -c "from meal_planner.core.staples import get_all, add, get_needed; print('OK')"`

**Step 5: Commit**

---

### Task 2: Migrate existing `is_staple` pantry items to `staples` table

**Files:**
- Modify: `meal_planner/db/database.py:106-129` (add migration logic after existing migrations)

**Step 1: Add migration code**

At the end of `init_db()`, after the existing migration loop (after line 127), add:

```python
# Migrate pantry is_staple items to standalone staples table
try:
    rows = conn.execute(
        "SELECT name, category, preferred_store_id FROM pantry WHERE is_staple = 1"
    ).fetchall()
    for row in rows:
        name = row["name"]
        # Only insert if not already in staples table
        existing = conn.execute(
            "SELECT id FROM staples WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO staples (name, category, preferred_store_id, need_to_buy) VALUES (?, ?, ?, 0)",
                (name, row["category"], row["preferred_store_id"]),
            )
    conn.commit()
except sqlite3.OperationalError:
    pass  # is_staple column may not exist yet on fresh installs
```

**Step 2: Remove `is_staple` from PantryItemDialog**

In `meal_planner/gui/pantry_tab.py`, remove the staple checkbox from the dialog:
- Remove `self.staple_check = QCheckBox(...)` (line 69)
- Remove `form.addRow("Staple:", self.staple_check)` (line 80)
- Remove `self.staple_check.setChecked(...)` from `_populate()` (line 118)
- Remove `is_staple = self.staple_check.isChecked()` from `get_item()` (line 158)
- Remove `is_staple=is_staple` from the PantryItem constructor in `get_item()` (line 173)

Note: Keep the `is_staple` field on the PantryItem dataclass and the DB column — SQLite can't drop columns. The field just won't be actively used by new code.

**Step 3: Update shopping list to use `staples` table instead of pantry `is_staple`**

In `meal_planner/core/shopping_list.py`, replace the pantry-based staple logic. Change the pantry query back to not select `is_staple`:

```python
pantry_rows = conn.execute(
    "SELECT name, quantity, estimated_price FROM pantry"
).fetchall()
```

Remove the `staple_names` set that reads from pantry rows. Instead, build it from the staples table:

```python
staple_rows = conn.execute(
    "SELECT name FROM staples WHERE need_to_buy = 0"
).fetchall()
staple_names = {row["name"].lower().strip() for row in staple_rows}
```

This means: staples where `need_to_buy = False` (user says "I have it") are excluded from the shopping list. Staples where `need_to_buy = True` will be handled in a later task.

**Step 4: Verify**

Run: `python3 -c "from meal_planner.core.shopping_list import generate; from meal_planner.gui.pantry_tab import PantryItemDialog; print('OK')"`

**Step 5: Commit**

---

### Task 3: Build the Manage Staples dialog

**Files:**
- Modify: `meal_planner/gui/pantry_tab.py` (add ManageStaplesDialog class and button)

**Step 1: Add "Manage Staples" button to PantryTab toolbar**

In `PantryTab.__init__()`, after the existing toolbar (around line 209), add a second toolbar row:

```python
toolbar2 = QHBoxLayout()
staples_btn = QPushButton("Manage Staples")
staples_btn.clicked.connect(self._manage_staples)
toolbar2.addWidget(staples_btn)
toolbar2.addStretch()
layout.addLayout(toolbar2)
```

**Step 2: Add `_manage_staples()` handler to PantryTab**

```python
def _manage_staples(self):
    """Open the Manage Staples dialog."""
    dlg = ManageStaplesDialog(parent=self)
    dlg.exec()
```

**Step 3: Create ManageStaplesDialog class**

Add this class to `meal_planner/gui/pantry_tab.py` (after PantryItemDialog, before PantryTab):

```python
class StapleEditDialog(QDialog):
    """Small dialog for adding or editing a single staple."""

    def __init__(self, staple=None, parent=None):
        super().__init__(parent)
        from meal_planner.db.models import Staple
        self.setWindowTitle("Edit Staple" if staple else "Add Staple")
        self.setMinimumWidth(350)
        self._staple = staple

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.category_edit = QLineEdit()

        stores = [s.name for s in pantry_core.get_all_stores()]
        self.store_combo = QComboBox()
        self.store_combo.setEditable(True)
        self.store_combo.addItem("")
        self.store_combo.addItems(stores)

        form.addRow("Name *:", self.name_edit)
        form.addRow("Category:", self.category_edit)
        form.addRow("Store:", self.store_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if staple:
            self.name_edit.setText(staple.name or "")
            self.category_edit.setText(staple.category or "")
            if staple.preferred_store_id:
                all_stores = pantry_core.get_all_stores()
                for s in all_stores:
                    if s.id == staple.preferred_store_id:
                        idx = self.store_combo.findText(s.name)
                        if idx >= 0:
                            self.store_combo.setCurrentIndex(idx)
                        break

    def _validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def get_staple(self):
        from meal_planner.db.models import Staple
        from meal_planner.db.database import get_connection

        store_name = self.store_combo.currentText().strip()
        store_id = None
        if store_name:
            conn = get_connection()
            try:
                row = conn.execute("SELECT id FROM stores WHERE name = ?", (store_name,)).fetchone()
                if row:
                    store_id = row["id"]
                else:
                    cur = conn.execute("INSERT INTO stores (name) VALUES (?)", (store_name,))
                    conn.commit()
                    store_id = cur.lastrowid
            finally:
                conn.close()

        return Staple(
            id=self._staple.id if self._staple else None,
            name=self.name_edit.text().strip(),
            category=self.category_edit.text().strip() or None,
            preferred_store_id=store_id,
            need_to_buy=self._staple.need_to_buy if self._staple else False,
        )


class ManageStaplesDialog(QDialog):
    """Dialog for viewing and managing the staples list.

    Shows all staples with Have/Need toggles, plus Add/Edit/Delete controls.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from meal_planner.core import staples as staples_core
        self._staples_core = staples_core

        self.setWindowTitle("Manage Staples")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Items you normally keep on hand. Toggle 'Need to Buy' when you run out."))

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Category", "Store", "Need to Buy"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Staple")
        add_btn.clicked.connect(self._add_staple)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_staple)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_staple)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self._refresh()

    def _refresh(self):
        staples = self._staples_core.get_all()
        all_stores = pantry_core.get_all_stores()
        store_map = {s.id: s.name for s in all_stores}

        self.table.setRowCount(len(staples))
        self._staple_ids = []
        for row, s in enumerate(staples):
            self._staple_ids.append(s.id)
            self.table.setItem(row, 0, QTableWidgetItem(s.name))
            self.table.setItem(row, 1, QTableWidgetItem(s.category or ""))
            self.table.setItem(row, 2, QTableWidgetItem(store_map.get(s.preferred_store_id, "")))

            # Need to buy checkbox
            cb = QCheckBox()
            cb.setChecked(s.need_to_buy)
            cb.stateChanged.connect(lambda state, sid=s.id: self._toggle_need(sid, state))
            widget = QWidget()
            cb_layout = QHBoxLayout(widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 3, widget)

    def _toggle_need(self, staple_id, state):
        self._staples_core.set_need_to_buy(staple_id, state == Qt.Checked.value)

    def _add_staple(self):
        dlg = StapleEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            staple = dlg.get_staple()
            existing = self._staples_core.get_by_name(staple.name)
            if existing:
                QMessageBox.information(self, "Exists", f"'{staple.name}' is already a staple.")
                return
            self._staples_core.add(staple)
            self._refresh()

    def _edit_staple(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._staple_ids):
            QMessageBox.information(self, "Edit", "Select a staple to edit.")
            return
        staple = self._staples_core.get(self._staple_ids[row])
        if not staple:
            return
        dlg = StapleEditDialog(staple, parent=self)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.get_staple()
            self._staples_core.update(updated)
            self._refresh()

    def _delete_staple(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._staple_ids):
            QMessageBox.information(self, "Delete", "Select a staple to delete.")
            return
        name = self.table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Confirm Delete", f"Remove '{name}' from staples?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._staples_core.delete(self._staple_ids[row])
            self._refresh()
```

**Step 4: Add QWidget import if missing**

Check that `QWidget` is in the imports at the top of `pantry_tab.py`. It should already be there.

**Step 5: Verify**

Run: `python3 -c "from meal_planner.gui.pantry_tab import ManageStaplesDialog; print('OK')"`

**Step 6: Commit**

---

### Task 4: Add "Mark as Staple" to RecipeEditDialog

**Files:**
- Modify: `meal_planner/gui/recipes_tab.py` (RecipeEditDialog — add context menu on ingredients table)

**Step 1: Enable context menu on ingredients table**

In `RecipeEditDialog.__init__()`, after the ingredients table setup (around line 380), add:

```python
self.ingredients_table.setContextMenuPolicy(Qt.CustomContextMenu)
self.ingredients_table.customContextMenuRequested.connect(self._ing_context_menu)
```

**Step 2: Add context menu handler**

Add to RecipeEditDialog:

```python
def _ing_context_menu(self, pos):
    """Show context menu for ingredient rows."""
    row = self.ingredients_table.rowAt(pos.y())
    if row < 0:
        return
    name_item = self.ingredients_table.item(row, 2)
    if not name_item or not name_item.text().strip():
        return

    from PySide6.QtWidgets import QMenu, QInputDialog
    menu = QMenu(self)
    mark_action = menu.addAction("Mark as Staple")
    action = menu.exec(self.ingredients_table.viewport().mapToGlobal(pos))

    if action == mark_action:
        self._mark_as_staple(row)

def _mark_as_staple(self, row):
    """Mark the ingredient at the given row as a staple."""
    from meal_planner.core import staples as staples_core

    name_item = self.ingredients_table.item(row, 2)
    raw_name = name_item.text().strip()

    # Use normalized shopping name if available
    suggested_name = raw_name
    if hasattr(self, '_normalized_data') and self._normalized_data and row < len(self._normalized_data):
        norm = self._normalized_data[row]
        if norm.get("shopping_name"):
            suggested_name = norm["shopping_name"]
    elif hasattr(self, '_original_shopping_data') and self._original_shopping_data and row < len(self._original_shopping_data):
        norm = self._original_shopping_data[row]
        if norm.get("shopping_name"):
            suggested_name = norm["shopping_name"]

    from PySide6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(
        self, "Mark as Staple",
        "Staple name (edit if needed):",
        text=suggested_name,
    )
    if not ok or not name.strip():
        return

    name = name.strip()
    existing = staples_core.get_by_name(name)
    if existing:
        QMessageBox.information(self, "Already a Staple", f"'{name}' is already in your staples list.")
        return

    from meal_planner.db.models import Staple
    staple = Staple(id=None, name=name)
    staples_core.add(staple)
    QMessageBox.information(self, "Staple Added", f"'{name}' added to your staples list.")
```

**Step 3: Verify**

Run: `python3 -c "from meal_planner.gui.recipes_tab import RecipeEditDialog; print('OK')"`

**Step 4: Commit**

---

### Task 5: Include staples needing purchase in shopping list

**Files:**
- Modify: `meal_planner/core/shopping_list.py:64-121` (generate function)

**Step 1: Add staples needing purchase to the shopping list output**

In `generate()`, after the main store_items loop (after line 118 — `store_items[store].sort(...)`) and before `return dict(store_items)`, add:

```python
# Add staples that need to be bought
staple_rows = conn.execute(
    """SELECT s.name, s.category, st.name as store_name
       FROM staples s
       LEFT JOIN stores st ON s.preferred_store_id = st.id
       WHERE s.need_to_buy = 1"""
).fetchall()
for row in staple_rows:
    store = row["store_name"] or "Staples"
    # Check if this staple is already in the list from a recipe
    staple_lower = row["name"].lower().strip()
    already_listed = any(
        item[0].lower().strip() == staple_lower
        for items in store_items.values()
        for item in items
    )
    if not already_listed:
        # Staples have no quantity/unit — just the name and no cost
        store_items[store].append((row["name"], 0, "", None))

# Re-sort after adding staples
for store in store_items:
    store_items[store].sort(key=lambda x: x[0])
```

**Step 2: Verify**

Run: `python3 -c "from meal_planner.core.shopping_list import generate; print('OK')"`

**Step 3: Commit**

---

### Task 6: Bulk delete in pantry — checkbox column + Delete Selected

**Files:**
- Modify: `meal_planner/core/pantry.py` (add `delete_many()`)
- Modify: `meal_planner/gui/pantry_tab.py` (PantryTab — add checkbox column, delete selected button)

**Step 1: Add `delete_many()` to pantry core**

In `meal_planner/core/pantry.py`, after `delete()`:

```python
def delete_many(item_ids: list[int]) -> int:
    """Delete multiple pantry items. Return count deleted."""
    if not item_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in item_ids)
        conn.execute(f"DELETE FROM pantry WHERE id IN ({placeholders})", item_ids)
        conn.commit()
        return len(item_ids)
    finally:
        conn.close()
```

**Step 2: Add checkbox column to PantryTab**

In `meal_planner/gui/pantry_tab.py`, update the COLUMNS list:

```python
COLUMNS = ["", "Name", "Brand", "Category", "Location", "Qty", "Unit", "Best By", "Store"]
```

The first column `""` is the checkbox column.

Update `COL_IDX`:
```python
COL_IDX = {name: i for i, name in enumerate(COLUMNS)}
```

**Step 3: Add "Delete Selected" button to toolbar**

In `PantryTab.__init__()`, add after the existing delete button (around line 208):

```python
self.delete_selected_btn = QPushButton("Delete Selected")
self.delete_selected_btn.clicked.connect(self._delete_selected)
self.delete_selected_btn.setEnabled(False)
```

And add it to the toolbar:
```python
toolbar.addWidget(self.delete_selected_btn)
```

**Step 4: Update `refresh()` to add checkboxes**

In the row-population loop in `refresh()`, add checkbox handling for column 0. Replace the current row setup with:

```python
for row, item in enumerate(items):
    self._item_ids.append(item.id)

    # Checkbox column
    cb = QCheckBox()
    cb.stateChanged.connect(self._update_delete_selected_state)
    widget = QWidget()
    cb_layout = QHBoxLayout(widget)
    cb_layout.addWidget(cb)
    cb_layout.setAlignment(Qt.AlignCenter)
    cb_layout.setContentsMargins(0, 0, 0, 0)
    self.table.setCellWidget(row, 0, widget)

    self.table.setItem(row, COL_IDX["Name"], QTableWidgetItem(item.name))
    # ... rest of columns with updated COL_IDX references ...
```

Update ALL column references in `refresh()` to use the new `COL_IDX` values (they're all shifted by 1).

Set the checkbox column width to be narrow:
```python
self.table.setColumnWidth(0, 30)
```

**Step 5: Add helper methods**

```python
def _update_delete_selected_state(self):
    """Enable/disable Delete Selected based on checkbox state."""
    count = self._get_checked_count()
    self.delete_selected_btn.setEnabled(count > 0)
    self.delete_selected_btn.setText(f"Delete Selected ({count})" if count > 0 else "Delete Selected")

def _get_checked_ids(self) -> list[int]:
    """Return item IDs for all checked rows."""
    checked = []
    for row in range(self.table.rowCount()):
        widget = self.table.cellWidget(row, 0)
        if widget:
            cb = widget.findChild(QCheckBox)
            if cb and cb.isChecked():
                checked.append(self._item_ids[row])
    return checked

def _get_checked_count(self) -> int:
    return len(self._get_checked_ids())

def _delete_selected(self):
    """Delete all checked pantry items after confirmation."""
    ids = self._get_checked_ids()
    if not ids:
        return
    reply = QMessageBox.question(
        self, "Confirm Delete",
        f"Delete {len(ids)} selected item(s) from pantry?",
        QMessageBox.Yes | QMessageBox.No,
    )
    if reply == QMessageBox.Yes:
        pantry_core.delete_many(ids)
        self.refresh()
```

**Step 6: Update `_delete_item` to account for column shift**

The existing `_delete_item` reads the name from column 0. Update to use `COL_IDX["Name"]`:

```python
name = self.table.item(row, COL_IDX["Name"]).text()
```

**Step 7: Verify**

Run: `python3 -c "from meal_planner.gui.pantry_tab import PantryTab; from meal_planner.core.pantry import delete_many; print('OK')"`

**Step 8: Commit**

---

### Task 7: Create `known_prices` table, model, and core CRUD

**Files:**
- Modify: `meal_planner/db/database.py` (add table + migration)
- Modify: `meal_planner/db/models.py` (add KnownPrice dataclass)
- Create: `meal_planner/core/known_prices.py`

**Step 1: Add `known_prices` table to schema**

In `meal_planner/db/database.py`, add to the `executescript` block:

```sql
CREATE TABLE IF NOT EXISTS known_prices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name    TEXT NOT NULL UNIQUE,
    unit_price   REAL NOT NULL,
    unit         TEXT,
    store_id     INTEGER REFERENCES stores(id),
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Step 2: Add KnownPrice dataclass**

In `meal_planner/db/models.py`, after `Staple`:

```python
@dataclass
class KnownPrice:
    """A known grocery price extracted from a receipt or entered manually.

    Used as the highest-priority price source for shopping list cost estimates.
    """
    id: Optional[int]
    item_name: str
    unit_price: float
    unit: Optional[str] = None
    store_id: Optional[int] = None
    last_updated: Optional[str] = None
```

**Step 3: Create `meal_planner/core/known_prices.py`**

```python
"""Known prices management — receipt-sourced grocery price data.

Prices in this table take priority over recipe ingredient prices and AI estimates
when calculating shopping list costs.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import KnownPrice


def get_all() -> list[KnownPrice]:
    """Return all known prices sorted by item name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM known_prices ORDER BY item_name").fetchall()
        return [KnownPrice(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_by_name(item_name: str) -> Optional[KnownPrice]:
    """Look up a known price by item name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
            (item_name.strip(),),
        ).fetchone()
        return KnownPrice(**dict(row)) if row else None
    finally:
        conn.close()


def upsert(item_name: str, unit_price: float, unit: str = None, store_id: int = None) -> None:
    """Insert or update a known price entry."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
            (item_name.strip(),),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE known_prices SET unit_price=?, unit=?, store_id=?,
                   last_updated=CURRENT_TIMESTAMP WHERE id=?""",
                (unit_price, unit, store_id, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO known_prices (item_name, unit_price, unit, store_id)
                   VALUES (?, ?, ?, ?)""",
                (item_name.strip(), unit_price, unit, store_id),
            )
        conn.commit()
    finally:
        conn.close()


def bulk_upsert(items: list[dict]) -> int:
    """Upsert multiple price entries. Each dict: {item_name, unit_price, unit, store_id}.
    Returns count of items processed."""
    conn = get_connection()
    try:
        count = 0
        for item in items:
            name = item["item_name"].strip()
            existing = conn.execute(
                "SELECT id FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
                (name,),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE known_prices SET unit_price=?, unit=?, store_id=?,
                       last_updated=CURRENT_TIMESTAMP WHERE id=?""",
                    (item["unit_price"], item.get("unit"), item.get("store_id"), existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO known_prices (item_name, unit_price, unit, store_id)
                       VALUES (?, ?, ?, ?)""",
                    (name, item["unit_price"], item.get("unit"), item.get("store_id")),
                )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def delete(price_id: int) -> None:
    """Delete a known price entry."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM known_prices WHERE id = ?", (price_id,))
        conn.commit()
    finally:
        conn.close()
```

**Step 4: Verify**

Run: `python3 -c "from meal_planner.core.known_prices import get_all, upsert, bulk_upsert; print('OK')"`

**Step 5: Commit**

---

### Task 8: Add receipt scanning AI function

**Files:**
- Modify: `meal_planner/core/ai_assistant.py` (add `parse_receipt_image()`)

**Step 1: Add `parse_receipt_image()` function**

Add after `normalize_ingredients()` in `meal_planner/core/ai_assistant.py`:

```python
def parse_receipt_image(image_paths: list[str]) -> list[dict]:
    """Extract item names and prices from receipt photo(s).

    Takes a list of file paths to receipt images (JPG/PNG).
    Returns list of dicts: [{"item_name": str, "price": float, "quantity": int}, ...]
    """
    import base64
    from pathlib import Path

    client = _get_client()

    content = []
    for path in image_paths:
        p = Path(path)
        suffix = p.suffix.lower()
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        with open(p, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })

    content.append({
        "type": "text",
        "text": """Extract all grocery items and their prices from this receipt.

For each item, provide:
- item_name: the product name (simplified to a common grocery name, e.g. "BLK BEANS 15OZ" -> "canned black beans")
- price: the total price paid for this item
- quantity: how many were purchased (default 1 if not clear)

Return a JSON array:
```json
[
  {"item_name": "canned black beans", "price": 1.29, "quantity": 2},
  {"item_name": "whole milk", "price": 4.99, "quantity": 1}
]
```

Ignore tax lines, subtotals, totals, and non-grocery items (bags, coupons, etc.).
Return only the JSON array, wrapped in ```json``` code fences."""
    })

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )

    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Validate and compute unit prices
    results = []
    for item in data:
        try:
            name = item.get("item_name", "").strip()
            price = float(item.get("price", 0))
            qty = int(item.get("quantity", 1))
            if name and price > 0 and qty > 0:
                results.append({
                    "item_name": name,
                    "total_price": price,
                    "quantity": qty,
                    "unit_price": round(price / qty, 2),
                })
        except (ValueError, TypeError):
            continue

    return results
```

**Step 2: Verify**

Run: `python3 -c "from meal_planner.core.ai_assistant import parse_receipt_image; print('OK')"`

**Step 3: Commit**

---

### Task 9: Add receipt scanning UI to Shopping tab

**Files:**
- Modify: `meal_planner/gui/shopping_tab.py` (add Scan Receipt button and review dialog)

**Step 1: Add "Scan Receipt" button to the export layout**

In `ShoppingTab.__init__()`, after the `clear_list_btn` (around line 185), add:

```python
scan_receipt_btn = QPushButton("Scan Receipt")
scan_receipt_btn.setToolTip("Extract prices from a receipt photo")
scan_receipt_btn.clicked.connect(self._scan_receipt)
export_layout.addWidget(scan_receipt_btn)
```

Add `QFileDialog` to the imports at the top of the file.

**Step 2: Add `_scan_receipt()` handler**

```python
def _scan_receipt(self):
    """Open file picker for receipt image(s) and extract prices."""
    from PySide6.QtWidgets import QFileDialog
    paths, _ = QFileDialog.getOpenFileNames(
        self, "Select Receipt Photo(s)", "",
        "Images (*.jpg *.jpeg *.png);;All Files (*)",
    )
    if not paths:
        return

    self.status_label.setText("Scanning receipt...")

    def do_scan():
        return ai_assistant.parse_receipt_image(paths)

    self._scan_worker = AIWorker(do_scan)
    self._scan_worker.finished.connect(self._receipt_scanned)
    self._scan_worker.error.connect(self._receipt_scan_error)
    self._scan_worker.start()

def _receipt_scanned(self, results):
    """Show review dialog with extracted receipt items."""
    self.status_label.setText("")
    if not results:
        QMessageBox.information(self, "No Items", "Could not extract any items from the receipt.")
        return
    dlg = ReceiptReviewDialog(results, parent=self)
    if dlg.exec() == QDialog.Accepted:
        items = dlg.get_items()
        if items:
            from meal_planner.core import known_prices
            count = known_prices.bulk_upsert(items)
            QMessageBox.information(self, "Prices Saved", f"Saved {count} price(s) from receipt.")

def _receipt_scan_error(self, msg):
    self.status_label.setText("")
    QMessageBox.warning(self, "Scan Error", msg)
```

**Step 3: Create ReceiptReviewDialog class**

Add to `meal_planner/gui/shopping_tab.py` (before ShoppingTab):

```python
class ReceiptReviewDialog(QDialog):
    """Review and edit prices extracted from a receipt before saving."""

    def __init__(self, items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Receipt Items")
        self.setMinimumSize(550, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Review extracted items. Edit or remove rows before saving."))

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Item Name", "Qty", "Total Price", "Unit Price"])
        from PySide6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item["item_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(item["quantity"])))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item['total_price']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{item['unit_price']:.2f}"))

        layout.addWidget(self.table)

        # Store selector
        from meal_planner.core import pantry as pantry_core
        store_layout = QHBoxLayout()
        store_layout.addWidget(QLabel("Store:"))
        self.store_combo = QComboBox()
        self.store_combo.setEditable(True)
        self.store_combo.addItem("")
        stores = [s.name for s in pantry_core.get_all_stores()]
        self.store_combo.addItems(stores)
        store_layout.addWidget(self.store_combo)
        store_layout.addStretch()
        layout.addLayout(store_layout)

        btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_row)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_layout.addWidget(buttons)
        layout.addLayout(btn_layout)

    def _remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def get_items(self) -> list[dict]:
        """Return the reviewed items as dicts for bulk_upsert."""
        from meal_planner.db.database import get_connection

        store_name = self.store_combo.currentText().strip()
        store_id = None
        if store_name:
            conn = get_connection()
            try:
                row = conn.execute("SELECT id FROM stores WHERE name = ?", (store_name,)).fetchone()
                if row:
                    store_id = row["id"]
                else:
                    cur = conn.execute("INSERT INTO stores (name) VALUES (?)", (store_name,))
                    conn.commit()
                    store_id = cur.lastrowid
            finally:
                conn.close()

        items = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            price_item = self.table.item(row, 3)  # unit price column
            if not name_item or not price_item:
                continue
            name = name_item.text().strip()
            try:
                unit_price = float(price_item.text())
            except ValueError:
                continue
            if name and unit_price > 0:
                items.append({
                    "item_name": name,
                    "unit_price": unit_price,
                    "unit": None,
                    "store_id": store_id,
                })
        return items
```

**Step 4: Add QComboBox to imports if not already there**

Check the imports at the top of `shopping_tab.py` and add `QComboBox` if missing.

**Step 5: Verify**

Run: `python3 -c "from meal_planner.gui.shopping_tab import ShoppingTab, ReceiptReviewDialog; print('OK')"`

**Step 6: Commit**

---

### Task 10: Integrate `known_prices` into shopping list price resolution

**Files:**
- Modify: `meal_planner/core/shopping_list.py:107-111` (price resolution in `generate()`)

**Step 1: Load known prices at the start of the buy loop**

In `generate()`, inside the `conn` block (after building `pantry_prices` around line 80), add:

```python
# Load known prices (highest priority)
known_price_rows = conn.execute(
    "SELECT item_name, unit_price FROM known_prices"
).fetchall()
known_prices = {
    row["item_name"].lower().strip(): row["unit_price"]
    for row in known_price_rows
}
```

**Step 2: Update price resolution**

Change the price resolution block (around lines 107-111) from:

```python
# Price resolution: recipe ingredient price > pantry price > None
unit_price = ingredient_prices.get((ing_name, unit))
if unit_price is None:
    unit_price = pantry_prices.get(ing_name)
```

To:

```python
# Price resolution: known price > recipe ingredient price > pantry price > None
unit_price = known_prices.get(ing_name)
if unit_price is None:
    unit_price = ingredient_prices.get((ing_name, unit))
if unit_price is None:
    unit_price = pantry_prices.get(ing_name)
```

**Step 3: Verify**

Run: `python3 -c "from meal_planner.core.shopping_list import generate; print('OK')"`

**Step 4: Commit**

---

## Summary of All Changes

| File | Change |
|------|--------|
| `db/database.py` | Add `staples` and `known_prices` tables to schema; migration for existing `is_staple` items |
| `db/models.py` | Add `Staple` and `KnownPrice` dataclasses |
| `core/staples.py` | **NEW** — Full CRUD + `set_need_to_buy()` + `get_needed()` |
| `core/known_prices.py` | **NEW** — CRUD + `upsert()` + `bulk_upsert()` |
| `core/pantry.py` | Add `delete_many()` |
| `core/ai_assistant.py` | Add `parse_receipt_image()` |
| `core/shopping_list.py` | Switch staple logic to `staples` table; add needed staples to output; add `known_prices` to price resolution |
| `gui/pantry_tab.py` | Remove staple checkbox from PantryItemDialog; add `ManageStaplesDialog` + `StapleEditDialog`; add checkbox column + Delete Selected to PantryTab |
| `gui/recipes_tab.py` | Add "Mark as Staple" context menu to RecipeEditDialog ingredients table |
| `gui/shopping_tab.py` | Add `ReceiptReviewDialog`; add "Scan Receipt" button + handlers |
