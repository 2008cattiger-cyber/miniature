from pathlib import Path


MEDIA_ROOT = Path("media/works")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

CATEGORY_TITLES = {
    "basket": "🧺 Корзины",
    "bear": "🧸 Мишки-Тедди",
    "closet": "🚪 Миниатюра на полку",
    "doll": "🪆 Куклы",
    "furniture": "🪑 Мебель",
    "miniature": "🏡 Другое",
    "newyear": "🎄 Новогодние",
    "roombox": "🛋️ Рум-бокс",
    "sea": "🌊 Море",
    "snowman": "❄️ Снеговики",
    "plants": "🌷 Растения",
}

CATEGORY_ORDER = [
    "basket",
    "bear",
    "closet",
    "doll",
    "furniture",
    "miniature",
    "newyear",
    "roombox",
    "sea",
    "snowman",
    "plants",
]


def get_categories():
    if not MEDIA_ROOT.exists():
        return []

    existing = {p.name for p in MEDIA_ROOT.iterdir() if p.is_dir()}
    categories = []

    for folder in CATEGORY_ORDER:
        if folder in existing:
            categories.append((folder, CATEGORY_TITLES.get(folder, folder)))

    for folder in sorted(existing - set(CATEGORY_ORDER)):
        categories.append((folder, CATEGORY_TITLES.get(folder, folder)))

    return categories


def list_category_photos(category):
    category_dir = MEDIA_ROOT / category
    if not category_dir.is_dir():
        return []

    files = [
        path for path in category_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]
    return sorted(files, key=lambda p: p.name.lower())
