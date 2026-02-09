"""Generate 50 seed products via the API."""

import random
import sys

import requests

random.seed(42)

BASE_URL = "http://localhost:8000"

# ----------------------------------------------------------------
# Category Configuration
# ----------------------------------------------------------------

CATEGORY_CFG = {
    "electronics": {
        "names": [
            "Compact Bluetooth Speaker",
            "Wireless Earbuds Pro",
            "USB-C Hub Adapter",
            "LED Desk Lamp",
            "Portable Power Bank 10000mAh",
            "Mechanical Keyboard",
            "Smart Plug Wi-Fi",
            "Noise Cancelling Headphones",
            "Wireless Charging Pad",
            "4K Webcam",
        ],
        "unit_types": ["piece"],
        "price_range": (5000, 150000),
        "topics": [
            {"topic": "Features", "description": "High-quality components with modern design and reliable performance.", "display_order": 0},
            {"topic": "Specifications", "description": "See product label for detailed technical specifications.", "display_order": 1},
        ],
        "variant_axes": [("Color", ["Black", "White", "Silver", "Blue"])],
        "dimension_ranges": {"width": (5.0, 30.0), "height": (3.0, 20.0), "depth": (2.0, 15.0)},
    },
    "fashion": {
        "names": [
            "Cotton Crew T-Shirt",
            "Classic Denim Jacket",
            "Lightweight Running Shoes",
            "Canvas Belt",
            "Merino Wool Beanie",
            "Linen Shorts",
            "Leather Crossbody Bag",
            "Silk Scarf",
            "Fleece Zip Hoodie",
            "Ankle Boots",
        ],
        "unit_types": ["piece", "pair"],
        "price_range": (1500, 45000),
        "topics": [
            {"topic": "Material", "description": "Premium materials selected for comfort and durability.", "display_order": 0},
            {"topic": "Care Instructions", "description": "Machine wash cold. Tumble dry low.", "display_order": 1},
        ],
        "variant_axes": [("Size", ["S", "M", "L", "XL"]), ("Color", ["Black", "Navy", "Grey", "White"])],
        "dimension_ranges": {"width": (20.0, 40.0), "height": (25.0, 50.0), "depth": (5.0, 15.0)},
    },
    "beauty": {
        "names": [
            "Hydrating Face Serum",
            "Matte Lipstick Set",
            "Charcoal Cleansing Mask",
            "Vitamin C Moisturizer",
            "Argan Oil Hair Treatment",
            "Retinol Night Cream",
            "Micellar Cleansing Water",
            "Volumizing Mascara",
            "Rose Water Toner",
            "Exfoliating Body Scrub",
        ],
        "unit_types": ["piece", "ml"],
        "price_range": (500, 15000),
        "topics": [
            {"topic": "Ingredients", "description": "Formulated with natural ingredients for gentle care.", "display_order": 0},
            {"topic": "How to Use", "description": "Apply evenly to clean skin. Use daily for best results.", "display_order": 1},
        ],
        "variant_axes": [("Size", ["30ml", "50ml", "100ml", "200ml"])],
        "dimension_ranges": {"width": (3.0, 10.0), "height": (5.0, 15.0), "depth": (3.0, 10.0)},
    },
    "home_garden": {
        "names": [
            "Ceramic Planter Set",
            "Bamboo Cutting Board",
            "Indoor Herb Garden Kit",
            "Stainless Steel Trash Can",
            "Cotton Throw Blanket",
            "Wall Mounted Shelf Set",
            "Scented Soy Candle",
            "Garden Tool Kit",
            "Memory Foam Pillow",
            "Glass Water Carafe",
        ],
        "unit_types": ["piece", "set"],
        "price_range": (2000, 100000),
        "topics": [
            {"topic": "Description", "description": "Designed to complement any home interior with practical functionality.", "display_order": 0},
            {"topic": "Dimensions", "description": "Check product label for exact measurements.", "display_order": 1},
        ],
        "variant_axes": [("Color", ["White", "Grey", "Green", "Brown"])],
        "dimension_ranges": {"width": (10.0, 50.0), "height": (10.0, 60.0), "depth": (5.0, 40.0)},
    },
    "sports_outdoors": {
        "names": [
            "Yoga Mat Premium",
            "Adjustable Dumbbell Set",
            "Camping Hammock",
            "Insulated Water Bottle",
            "Resistance Band Kit",
            "Jump Rope Speed",
            "Hiking Backpack 40L",
            "Foam Roller",
            "Cycling Gloves",
            "Portable Camping Stove",
        ],
        "unit_types": ["piece", "set"],
        "price_range": (2000, 80000),
        "topics": [
            {"topic": "Features", "description": "Built for performance and durability in any environment.", "display_order": 0},
            {"topic": "Usage", "description": "Suitable for indoor and outdoor activities.", "display_order": 1},
        ],
        "variant_axes": [("Size", ["S", "M", "L", "XL"]), ("Color", ["Black", "Red", "Blue"])],
        "dimension_ranges": {"width": (10.0, 60.0), "height": (5.0, 180.0), "depth": (5.0, 30.0)},
    },
    "food_beverage": {
        "names": [
            "Organic Green Tea Collection",
            "Dark Chocolate Assortment",
            "Cold Press Olive Oil",
            "Dried Fruit Mix",
            "Specialty Coffee Beans",
            "Raw Honey Jar",
            "Matcha Powder Premium",
            "Mixed Nut Butter",
            "Sparkling Water Variety Pack",
            "Quinoa Grain Bag",
        ],
        "unit_types": ["pack", "kg", "liter"],
        "price_range": (300, 10000),
        "topics": [
            {"topic": "Ingredients", "description": "Made from carefully sourced natural ingredients.", "display_order": 0},
            {"topic": "Storage", "description": "Store in a cool, dry place away from direct sunlight.", "display_order": 1},
        ],
        "variant_axes": [("Weight", ["250g", "500g", "1kg"])],
        "dimension_ranges": {"width": (5.0, 20.0), "height": (10.0, 30.0), "depth": (5.0, 15.0)},
    },
    "health_wellness": {
        "names": [
            "Daily Multivitamin",
            "Omega-3 Fish Oil Capsules",
            "Protein Powder Vanilla",
            "Probiotic Supplement",
            "Melatonin Sleep Aid",
            "Collagen Peptides Powder",
            "Electrolyte Drink Mix",
            "Zinc Immune Support",
            "Turmeric Curcumin Capsules",
            "Magnesium Glycinate",
        ],
        "unit_types": ["piece", "pack"],
        "price_range": (1000, 20000),
        "topics": [
            {"topic": "Benefits", "description": "Supports overall health and daily wellness goals.", "display_order": 0},
            {"topic": "Dosage", "description": "Take as directed on the label. Consult a healthcare professional.", "display_order": 1},
        ],
        "variant_axes": [("Count", ["30ct", "60ct", "90ct", "120ct"])],
        "dimension_ranges": {"width": (5.0, 15.0), "height": (8.0, 20.0), "depth": (5.0, 15.0)},
    },
    "toys_games": {
        "names": [
            "Wooden Building Blocks",
            "Strategy Board Game",
            "Remote Control Car",
            "Puzzle Set 1000 Pieces",
            "Plush Teddy Bear",
            "Magnetic Tile Building Set",
            "Card Game Starter Deck",
            "Play Dough Color Kit",
            "Dinosaur Figure Collection",
            "Marble Run Track",
        ],
        "unit_types": ["piece", "set"],
        "price_range": (500, 25000),
        "topics": [
            {"topic": "Description", "description": "Fun and engaging entertainment for the whole family.", "display_order": 0},
            {"topic": "Age Recommendation", "description": "See product label for recommended age group.", "display_order": 1},
        ],
        "variant_axes": [("Age Group", ["3+", "5+", "8+", "12+"])],
        "dimension_ranges": {"width": (10.0, 40.0), "height": (5.0, 30.0), "depth": (5.0, 25.0)},
    },
    "books_media": {
        "names": [
            "Cookbook Mediterranean Recipes",
            "Sci-Fi Novel Collection",
            "Photography Guide",
            "Language Learning Flashcards",
            "Travel Journal Notebook",
            "Mindfulness Coloring Book",
            "Business Strategy Handbook",
            "Art History Encyclopedia",
            "Kids Story Book Bundle",
            "Vinyl Record Classic Rock",
        ],
        "unit_types": ["piece", "set"],
        "price_range": (500, 5000),
        "topics": [
            {"topic": "Summary", "description": "An essential addition to any collection.", "display_order": 0},
        ],
        "variant_axes": [("Format", ["Paperback", "Hardcover"])],
        "dimension_ranges": {"width": (12.0, 22.0), "height": (18.0, 30.0), "depth": (1.0, 5.0)},
    },
    "automotive": {
        "names": [
            "Car Phone Mount",
            "Dash Cam HD",
            "Seat Cover Set",
            "LED Headlight Bulbs",
            "Tire Pressure Gauge",
            "Trunk Organizer",
            "Steering Wheel Cover",
            "Portable Jump Starter",
            "Car Air Freshener Set",
            "Windshield Sun Shade",
        ],
        "unit_types": ["piece", "pair", "set"],
        "price_range": (3000, 200000),
        "topics": [
            {"topic": "Compatibility", "description": "Designed for universal fitment across most vehicle types.", "display_order": 0},
            {"topic": "Installation", "description": "Easy installation with included hardware.", "display_order": 1},
        ],
        "variant_axes": [("Fitment", ["Universal", "Compact", "Mid-Size", "Full-Size"])],
        "dimension_ranges": {"width": (5.0, 50.0), "height": (5.0, 40.0), "depth": (3.0, 30.0)},
    },
    "other": {
        "names": [
            "Gift Card Holder",
            "Reusable Shopping Bag Set",
            "Custom Engraved Keychain",
            "Desk Organizer Tray",
            "Portable Umbrella",
        ],
        "unit_types": ["piece", "set"],
        "price_range": (1000, 50000),
        "topics": [
            {"topic": "Description", "description": "A versatile product for everyday use.", "display_order": 0},
        ],
        "variant_axes": [("Variant", ["Standard", "Premium"])],
        "dimension_ranges": {"width": (5.0, 30.0), "height": (5.0, 20.0), "depth": (2.0, 15.0)},
    },
}

# ----------------------------------------------------------------
# Location Templates (Israeli warehouses)
# ----------------------------------------------------------------

LOCATION_TEMPLATES = [
    {"location_name": "Tel Aviv Central Warehouse", "city": "Tel Aviv", "zip_code": "6100000", "country": "IL"},
    {"location_name": "Haifa Port Storage", "city": "Haifa", "zip_code": "3100000", "country": "IL"},
    {"location_name": "Beer Sheva Distribution Center", "city": "Be'er Sheva", "zip_code": "8400000", "country": "IL"},
    {"location_name": "Ashdod Logistics Hub", "city": "Ashdod", "zip_code": "7700000", "country": "IL"},
    {"location_name": "Petah Tikva Fulfillment Center", "city": "Petah Tikva", "zip_code": "4900000", "country": "IL"},
    {"location_name": "Netanya Storage Facility", "city": "Netanya", "zip_code": "4200000", "country": "IL"},
    {"location_name": "Jerusalem Warehouse", "city": "Jerusalem", "zip_code": "9100000", "country": "IL"},
    {"location_name": "Eilat Free Zone Storage", "city": "Eilat", "zip_code": "8800000", "country": "IL"},
]

# Status distribution: ~60% active, ~20% draft, ~10% out_of_stock, ~10% discontinued
STATUS_POOL = ["active"] * 6 + ["draft"] * 2 + ["out_of_stock"] * 1 + ["discontinued"] * 1

# ----------------------------------------------------------------
# Build product pool: list of (category, name) pairs
# ----------------------------------------------------------------

PRODUCT_POOL = []
for _cat, _cfg in CATEGORY_CFG.items():
    for _name in _cfg["names"]:
        PRODUCT_POOL.append((_cat, _name))

random.shuffle(PRODUCT_POOL)


def get_supplier_ids():
    resp = requests.get(f"{BASE_URL}/suppliers", params={"limit": 100})
    resp.raise_for_status()
    return [s["id"] for s in resp.json()]


def generate_product(index, category, name, supplier_id):
    cfg = CATEGORY_CFG[category]

    base_sku = f"SKU-{category[:3].upper()}-{index + 1:04d}"
    base_price = random.randint(*cfg["price_range"])

    # Stock locations (1-3)
    num_locations = random.randint(1, 3)
    selected_locations = random.sample(LOCATION_TEMPLATES, num_locations)
    stock_locations = []
    for j, loc in enumerate(selected_locations):
        stock_locations.append({
            "location_id": f"loc-{index + 1}-{j + 1}",
            "location_name": loc["location_name"],
            "city": loc["city"],
            "zip_code": loc["zip_code"],
            "country": loc["country"],
            "quantity": random.randint(10, 500),
        })

    # Variants (0-5)
    variants = {}
    num_variants = random.randint(0, 5)
    if num_variants > 0 and cfg["variant_axes"]:
        axis_name, axis_values = random.choice(cfg["variant_axes"])
        count = min(num_variants, len(axis_values))
        selected_values = random.sample(axis_values, count)
        for k, val in enumerate(selected_values):
            vid = f"var-{k + 1}"
            dim = cfg["dimension_ranges"]
            variant_price = int(base_price * random.uniform(0.8, 1.3))
            variants[val] = {
                "variant_id": vid,
                "variant_name": val,
                "attributes": [{"attribute_name": axis_name, "attribute_value": val}],
                "sku": f"{base_sku}-{vid}",
                "price_cents": variant_price,
                "quantity": random.randint(5, 200),
                "package_dimensions": {
                    "width_cm": round(random.uniform(*dim["width"]), 1),
                    "height_cm": round(random.uniform(*dim["height"]), 1),
                    "depth_cm": round(random.uniform(*dim["depth"]), 1),
                    "weight_grams": random.randint(100, 5000),
                },
            }

    body = {
        "name": name,
        "category": category,
        "unit_type": random.choice(cfg["unit_types"]),
        "base_sku": base_sku,
        "base_price_cents": base_price,
        "topic_descriptions": cfg["topics"],
        "stock_locations": stock_locations,
        "variants": variants,
        "images": [{"url": "https://placehold.co/400x400"}],
        "shipping": {"ships_from_country": "IL"},
    }

    resp = requests.post(
        f"{BASE_URL}/products",
        headers={"X-Supplier-ID": supplier_id},
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    product_id = data["id"]

    # Status transitions
    target_status = random.choice(STATUS_POOL)
    if target_status in ("active", "out_of_stock", "discontinued"):
        requests.post(
            f"{BASE_URL}/products/{product_id}/publish",
            headers={"X-Supplier-ID": supplier_id},
        ).raise_for_status()
    if target_status == "out_of_stock":
        requests.post(
            f"{BASE_URL}/products/{product_id}/mark-out-of-stock",
            headers={"X-Supplier-ID": supplier_id},
        ).raise_for_status()
    if target_status == "discontinued":
        requests.post(
            f"{BASE_URL}/products/{product_id}/discontinue",
            headers={"X-Supplier-ID": supplier_id},
        ).raise_for_status()

    print(f"Product [{index + 1}/50] created: {product_id} ({name}) [{target_status}]")
    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate seed products via the API.")
    parser.add_argument("--count", type=int, default=50, help="Number of products to create")
    parser.add_argument("--skip", type=int, default=0, help="Offset into the product pool")
    args = parser.parse_args()

    batch = PRODUCT_POOL[args.skip : args.skip + args.count]
    if not batch:
        print(f"No products in pool at offset {args.skip}. Pool size: {len(PRODUCT_POOL)}")
        sys.exit(1)

    supplier_ids = get_supplier_ids()
    if not supplier_ids:
        print("No suppliers found. Run seed.py first.")
        sys.exit(1)

    total = len(batch)
    for i, (cat, product_name) in enumerate(batch):
        sid = random.choice(supplier_ids)
        generate_product(args.skip + i, cat, product_name, sid)

    print(f"\nDone. {total} products created.")
