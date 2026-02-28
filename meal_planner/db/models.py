"""Dataclass models for all database entities.

Each class maps 1:1 to a database table. Fields use Optional types for
nullable columns. These are plain data containers with no business logic.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Store:
    """A store/shop where ingredients can be purchased."""
    id: Optional[int]
    name: str
    location: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class PantryItem:
    """A pantry inventory item, imported from PantryChecker CSV or added manually.

    Location is one of 'Pantry', 'Fridge', or 'Freezer'.
    Dates (stocked_date, best_by) are stored as ISO YYYY-MM-DD strings.
    """

    id: Optional[int]
    name: str
    barcode: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None  # Pantry, Fridge, Freezer
    brand: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None
    stocked_date: Optional[str] = None
    best_by: Optional[str] = None
    preferred_store_id: Optional[int] = None
    product_notes: Optional[str] = None
    item_notes: Optional[str] = None
    estimated_price: Optional[float] = None
    is_staple: bool = False


@dataclass
class RecipeIngredient:
    """A single ingredient line within a recipe (e.g. '2 lbs chicken breast')."""

    id: Optional[int]
    recipe_id: Optional[int]
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    estimated_price: Optional[float] = None
    shopping_name: Optional[str] = None
    shopping_qty: Optional[float] = None
    shopping_unit: Optional[str] = None


@dataclass
class Recipe:
    """A recipe with metadata and an embedded list of RecipeIngredient items.

    Tags are stored as a comma-separated string (e.g. 'chicken,quick,dinner').
    The ingredients list is populated by core/recipes.py when loading from the DB.
    """

    id: Optional[int]
    name: str
    description: Optional[str] = None
    servings: int = 4
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    instructions: Optional[str] = None
    source_url: Optional[str] = None
    tags: Optional[str] = None
    rating: Optional[int] = None
    created_at: Optional[str] = None
    ingredients: list = field(default_factory=list)  # list[RecipeIngredient]


@dataclass
class MealPlanEntry:
    """A single cell in the meal plan grid: one date + one meal slot.

    recipe_name is a display-only field joined from the recipes table and is
    not written back to the database.
    """

    id: Optional[int]
    date: str  # ISO YYYY-MM-DD
    meal_slot: str  # Breakfast, Lunch, Dinner, Snack
    recipe_id: Optional[int] = None
    servings: int = 1
    notes: Optional[str] = None
    recipe_name: Optional[str] = None  # Joined from recipes table for display


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
