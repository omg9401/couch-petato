"""
Couch Petato — Local Product Manager
Run:  python app.py
Open: http://localhost:5001
"""

import os, sys, uuid, sqlite3, json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Load .env from the project root (one level up from gui/)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass  # dotenv not installed — rely on real env vars

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg
import sku_generator as sku_gen

BASE_DIR   = Path(__file__).parent
PROJ_DIR   = BASE_DIR.parent
DB_PATH    = PROJ_DIR / "database" / "couch_petato.db"
UPLOAD_DIR = PROJ_DIR / "uploads"
ALLOWED    = {"png", "jpg", "jpeg", "pdf"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


# ─────────────────────────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────────────────────────────

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        product_number        TEXT    UNIQUE NOT NULL,
        sku                   TEXT,
        name                  TEXT    NOT NULL,
        status                TEXT    DEFAULT 'DRAFT',
        size_variation        TEXT,
        size                  TEXT,
        dimensions            TEXT,
        description           TEXT,
        weight_kg             REAL,
        cubic_volume          TEXT,
        wood_options_note     TEXT,
        leg_options_note      TEXT,
        cushion_variation     TEXT,
        fabric_color_count    INTEGER,
        shopify_product_id    TEXT,
        created_at            TEXT    DEFAULT (datetime('now')),
        updated_at            TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS variants (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_number        TEXT    UNIQUE NOT NULL,
        base_product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        variant_sku           TEXT,
        status                TEXT    DEFAULT 'DRAFT',
        fabric_color_name     TEXT,
        fabric_code           TEXT,
        fabric_type           TEXT    DEFAULT 'PLN',
        fabric_code_link      TEXT,
        wood_option           TEXT,
        leg_option            TEXT,
        material_cost         REAL,
        fabric_qty            REAL,
        fabric_cost           REAL,
        labour_hours          REAL,
        labour_persons        INTEGER DEFAULT 1,
        labour_cost           REAL,
        soc                   REAL,
        profit                REAL,
        product_sp            REAL,
        packaging_cost        REAL    DEFAULT 55,
        shipping_cost         REAL    DEFAULT 100,
        external_costs        REAL,
        listed_price          REAL,
        royalties             REAL,
        listed_pre_vat        REAL,
        listed_with_vat       REAL,
        final_price           REAL,
        shopify_variant_id    TEXT,
        shopify_synced_at     TEXT,
        notes                 TEXT,
        created_at            TEXT    DEFAULT (datetime('now')),
        updated_at            TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS files (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type   TEXT NOT NULL,
        entity_id     INTEGER NOT NULL,
        file_category TEXT DEFAULT 'image',
        filename      TEXT NOT NULL,
        original_name TEXT,
        mime_type     TEXT,
        created_at    TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id   INTEGER NOT NULL,
        label       TEXT,
        url         TEXT NOT NULL,
        created_at  TEXT DEFAULT (datetime('now'))
    );
    """)
    # Migrate: add columns and tables introduced after initial schema
    for ddl in [
        "ALTER TABLE products ADD COLUMN model_abbr TEXT",
        "ALTER TABLE products ADD COLUMN manufacturer TEXT",
        "ALTER TABLE variants ADD COLUMN supplier_abbr TEXT",
        "ALTER TABLE variants ADD COLUMN finish_code TEXT",
        "ALTER TABLE products ADD COLUMN default_material_cost REAL",
        "ALTER TABLE products ADD COLUMN default_fabric_qty REAL",
        "ALTER TABLE products ADD COLUMN default_fabric_rate REAL DEFAULT 50",
        "ALTER TABLE products ADD COLUMN default_labour_hours REAL",
        "ALTER TABLE products ADD COLUMN default_labour_persons INTEGER DEFAULT 1",
        "ALTER TABLE products ADD COLUMN default_profit_pct REAL DEFAULT 60",
        "ALTER TABLE products ADD COLUMN ext_cost_box REAL DEFAULT 30",
        "ALTER TABLE products ADD COLUMN ext_cost_bubble REAL DEFAULT 10",
        "ALTER TABLE products ADD COLUMN ext_cost_stickers REAL DEFAULT 15",
        "ALTER TABLE products ADD COLUMN ext_cost_emboss REAL DEFAULT 20",
        "ALTER TABLE products ADD COLUMN ext_cost_notecard REAL DEFAULT 20",
        "ALTER TABLE products ADD COLUMN ext_cost_patch REAL DEFAULT 20",
        "ALTER TABLE products ADD COLUMN ext_cost_shipping REAL DEFAULT 100",
        "ALTER TABLE products ADD COLUMN ext_profit_pct REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN royalties_pct REAL DEFAULT 7",
        "ALTER TABLE products ADD COLUMN vat_pct REAL DEFAULT 5",
        "ALTER TABLE products ADD COLUMN fabric_manufacturer TEXT",
        "ALTER TABLE products ADD COLUMN fabric_base_code TEXT",
        "ALTER TABLE products ADD COLUMN fabric_base_link TEXT",
        "ALTER TABLE variants ADD COLUMN size TEXT",
        "ALTER TABLE variants ADD COLUMN fabric_rate REAL",
        "ALTER TABLE variants ADD COLUMN profit_pct REAL DEFAULT 60",
        "ALTER TABLE product_options ADD COLUMN cost REAL",
        "ALTER TABLE product_options ADD COLUMN dimensions TEXT",
        "ALTER TABLE product_options ADD COLUMN weight_kg REAL",
        "ALTER TABLE product_options ADD COLUMN cubic_volume TEXT",
        "ALTER TABLE product_options ADD COLUMN wood_cost REAL",
        "ALTER TABLE product_options ADD COLUMN fabric_qty REAL",
        "ALTER TABLE product_options ADD COLUMN labour_hours REAL",
        "ALTER TABLE product_options ADD COLUMN labour_persons INTEGER DEFAULT 1",
        "ALTER TABLE product_options ADD COLUMN foam_cost REAL",
        "ALTER TABLE product_options ADD COLUMN filling_type TEXT",
        "ALTER TABLE product_options ADD COLUMN link TEXT",
        "ALTER TABLE product_options ADD COLUMN supplier TEXT",
        "ALTER TABLE product_options ADD COLUMN is_patterned INTEGER DEFAULT 0",
        "ALTER TABLE product_options ADD COLUMN meta TEXT",
        "ALTER TABLE product_options ADD COLUMN stock_metres REAL",
        "ALTER TABLE product_options ADD COLUMN stock_status TEXT",
        "ALTER TABLE product_options ADD COLUMN stock_updated_at TEXT",
        "ALTER TABLE variants ADD COLUMN shopify_inventory_item_id TEXT",
        """CREATE TABLE IF NOT EXISTS product_options (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            option_type TEXT    NOT NULL,
            sort_order  INTEGER DEFAULT 0,
            value       TEXT,
            code        TEXT,
            cost        REAL,
            dimensions  TEXT,
            weight_kg   REAL,
            cubic_volume TEXT,
            wood_cost   REAL
        )""",
    ]:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def unique_variant_sku(conn, base_sku, exclude_vid=None):
    """Return base_sku or base_sku-2, -3 … to ensure uniqueness."""
    sku, counter = base_sku, 1
    while True:
        q = "SELECT id FROM variants WHERE variant_sku=?"
        params = [sku]
        if exclude_vid:
            q += " AND id!=?"
            params.append(exclude_vid)
        if not conn.execute(q, params).fetchone():
            return sku
        counter += 1
        sku = f"{base_sku}-{counter}"


def unique_model_abbr(conn, name, exclude_pid=None):
    """Generate a unique model abbreviation, handling hyphens/numbers/special chars.
    'Cami Round' → 'CR', if taken → 'CARO', if taken → 'CAMROU', …
    'Bed-3 Pro'  → 'B3P', …
    """
    import re as _re
    raw_words = [w for w in _re.split(r"[\s\-_/]+", name.upper()) if w]
    # Strip non-alphanumeric from each word, keep only words with at least one alnum char
    words = []
    for w in raw_words:
        clean = "".join(ch for ch in w if ch.isalnum())
        if clean:
            words.append(clean)
    if not words:
        return ""
    for letters_per_word in range(1, max(len(w) for w in words) + 1):
        abbr = "".join(w[:letters_per_word] for w in words)
        q = "SELECT id FROM products WHERE model_abbr=?"
        params = [abbr]
        if exclude_pid:
            q += " AND id!=?"
            params.append(exclude_pid)
        if not conn.execute(q, params).fetchone():
            return abbr
    return "".join(w for w in words)  # fallback


# ─────────────────────────────────────────────────────────────────
#  Pricing Calculator
# ─────────────────────────────────────────────────────────────────

def calculate_pricing(data):
    try:
        mat        = float(data.get("material_cost")  or 0)
        qty        = float(data.get("fabric_qty")     or 0)
        fabric_rate= float(data.get("fabric_rate")    or cfg.FABRIC_RATE_PER_METRE)
        hrs        = float(data.get("labour_hours")   or 0)
        persons    = int(data.get("labour_persons")   or 1)
        profit_pct = float(data.get("profit_pct")     or cfg.PROFIT_MARGIN * 100) / 100

        # Product costs (left)
        fabric_cost   = round(qty * fabric_rate, 2)
        labour_cost   = round(hrs * persons * cfg.LABOUR_RATE_PER_PERSON_HOUR, 2)
        soc           = round(mat + fabric_cost + labour_cost, 2)
        profit        = round(soc * profit_pct, 2)
        product_sp    = round(soc + profit, 2)

        # External costs (right)
        ext_costs     = round(cfg.PACKAGING_TOTAL + cfg.SHIPPING_TO_WAREHOUSE, 2)

        # Combined
        listed        = round(product_sp + ext_costs, 2)
        royalties     = round(listed * cfg.ROYALTIES_RATE, 2)
        pre_vat       = round(listed + royalties, 2)
        vat_amount    = round(pre_vat * cfg.VAT_RATE, 2)
        with_vat      = round(pre_vat + vat_amount, 2)

        return {
            "fabric_cost":      fabric_cost,
            "labour_cost":      labour_cost,
            "soc":              soc,
            "profit":           profit,
            "product_sp":       product_sp,
            "packaging_cost":   cfg.PACKAGING_TOTAL,
            "shipping_cost":    cfg.SHIPPING_TO_WAREHOUSE,
            "external_costs":   ext_costs,
            "listed_price":     listed,
            "royalties":        royalties,
            "listed_pre_vat":   pre_vat,
            "listed_with_vat":  with_vat,
        }
    except (TypeError, ValueError):
        return {}


# ─────────────────────────────────────────────────────────────────
#  Routes — Static
# ─────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/admin")
def index():
    return render_template("index.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)

@app.route("/api/products/summary")
def products_summary():
    conn = get_db()
    rows = conn.execute("SELECT * FROM products ORDER BY CAST(product_number AS REAL)").fetchall()
    result = []
    for p in rows:
        d = dict(p)
        vs = conn.execute(
            "SELECT final_price, status FROM variants WHERE base_product_id=?", (p["id"],)
        ).fetchall()
        prices = [v["final_price"] for v in vs if v["final_price"]]
        d["variant_count"]   = len(vs)
        d["active_variants"] = sum(1 for v in vs if v["status"] == "ACTIVE")
        d["min_price"]       = round(min(prices), 2) if prices else None
        d["max_price"]       = round(max(prices), 2) if prices else None
        result.append(d)
    conn.close()
    return jsonify(result)


@app.route("/api/products/<int:pid>/options", methods=["GET"])
def get_product_options(pid):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM product_options WHERE product_id=? ORDER BY option_type, sort_order",
        (pid,)
    ).fetchall()
    conn.close()
    grouped = {}
    for r in rows:
        t = r["option_type"]
        grouped.setdefault(t, []).append(dict(r))
    return jsonify(grouped)


@app.route("/api/products/<int:pid>/options", methods=["PUT"])
def save_product_options(pid):
    """
    Upsert product options preserving IDs for stable file attachments.
    - subvar options:  matched by (product_id, option_type, value) — composite key
    - all other types: matched by (product_id, option_type, sort_order)
    Orphaned records are deleted at the end.
    """
    data = request.json or {}
    conn = get_db()

    for opt_type, items in data.items():
        # Fetch existing records for this type
        existing = {
            row["value"]: row["id"] if opt_type == "subvar" else None
            for row in conn.execute(
                "SELECT id, value FROM product_options WHERE product_id=? AND option_type=?",
                (pid, opt_type)
            ).fetchall()
        }
        existing_by_order = {
            row["sort_order"]: row["id"]
            for row in conn.execute(
                "SELECT id, sort_order FROM product_options WHERE product_id=? AND option_type=?",
                (pid, opt_type)
            ).fetchall()
        }

        seen_ids = set()

        for i, item in enumerate(items):
            if isinstance(item, str):
                val, obj = item, {}
            else:
                val, obj = item.get("value", ""), item
            if not val:
                continue

            params = (
                pid, opt_type, i, val,
                obj.get("code"), obj.get("cost"),
                obj.get("dimensions"), obj.get("weight_kg"), obj.get("cubic_volume"),
                obj.get("wood_cost"), obj.get("fabric_qty"), obj.get("labour_hours"),
                obj.get("labour_persons", 1), obj.get("foam_cost"),
                obj.get("filling_type"), obj.get("link"),
                obj.get("supplier"), obj.get("is_patterned", 0), obj.get("meta"),
            )

            if opt_type == "subvar":
                existing_id = existing.get(val)
            else:
                existing_id = existing_by_order.get(i)

            if existing_id:
                conn.execute("""
                    UPDATE product_options SET
                        sort_order=?, value=?, code=?, cost=?,
                        dimensions=?, weight_kg=?, cubic_volume=?, wood_cost=?,
                        fabric_qty=?, labour_hours=?, labour_persons=?,
                        foam_cost=?, filling_type=?, link=?,
                        supplier=?, is_patterned=?, meta=?
                    WHERE id=?
                """, (i, val, obj.get("code"), obj.get("cost"),
                      obj.get("dimensions"), obj.get("weight_kg"), obj.get("cubic_volume"),
                      obj.get("wood_cost"), obj.get("fabric_qty"), obj.get("labour_hours"),
                      obj.get("labour_persons", 1), obj.get("foam_cost"),
                      obj.get("filling_type"), obj.get("link"),
                      obj.get("supplier"), obj.get("is_patterned", 0), obj.get("meta"),
                      existing_id))
                # NOTE: stock_metres / stock_status / stock_updated_at are NOT touched here —
                # they are written only by the scraper endpoint, never by a product save.
                seen_ids.add(existing_id)
            else:
                cur = conn.execute("""
                    INSERT INTO product_options
                        (product_id, option_type, sort_order, value, code, cost,
                         dimensions, weight_kg, cubic_volume, wood_cost,
                         fabric_qty, labour_hours, labour_persons,
                         foam_cost, filling_type, link,
                         supplier, is_patterned, meta)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, params)
                seen_ids.add(cur.lastrowid)

        # Delete orphans (removed by user)
        if seen_ids:
            placeholders = ",".join("?" * len(seen_ids))
            conn.execute(
                f"DELETE FROM product_options WHERE product_id=? AND option_type=? AND id NOT IN ({placeholders})",
                (pid, opt_type, *seen_ids)
            )
        else:
            conn.execute(
                "DELETE FROM product_options WHERE product_id=? AND option_type=?",
                (pid, opt_type)
            )

    conn.commit()
    # Return the saved options with their IDs so the UI can use them for file uploads
    rows = conn.execute(
        "SELECT * FROM product_options WHERE product_id=? ORDER BY option_type, sort_order",
        (pid,)
    ).fetchall()
    conn.close()
    grouped = {}
    for r in rows:
        grouped.setdefault(r["option_type"], []).append(dict(r))
    return jsonify({"ok": True, "options": grouped})


@app.route("/api/sku/preview")
def sku_preview():
    name   = request.args.get("name","")
    m      = request.args.get("model_abbr") or sku_gen.model_abbr(name)
    sup    = request.args.get("supplier_abbr","")
    color  = request.args.get("fabric_code","")
    finish = request.args.get("finish_code","")
    return jsonify({
        "model_abbr":    m,
        "product_sku":   sku_gen.product_sku(m),
        "color_abbr":    sku_gen.color_abbr(color),
        "variant_sku":   sku_gen.variant_sku(m, sup, color, finish),
    })


# ─────────────────────────────────────────────────────────────────
#  Routes — Products
# ─────────────────────────────────────────────────────────────────

@app.route("/api/products", methods=["GET"])
def list_products():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM products ORDER BY CAST(product_number AS REAL)"
    ).fetchall()
    result = []
    for p in rows:
        d = dict(p)
        vs = conn.execute(
            "SELECT * FROM variants WHERE base_product_id=? ORDER BY variant_number",
            (p["id"],)
        ).fetchall()
        d["variants"] = [dict(v) for v in vs]
        result.append(d)
    conn.close()
    return jsonify(result)


@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.json or {}
    conn = get_db()
    mx = conn.execute("SELECT MAX(CAST(product_number AS REAL)) FROM products").fetchone()[0]
    num = str(int(mx + 1) if mx else 1)

    name   = data.get("name", "New Product")
    m_abbr = data.get("model_abbr") or unique_model_abbr(conn, name)
    sku    = data.get("sku") or sku_gen.product_sku(m_abbr)

    cur = conn.execute("""
        INSERT INTO products
            (product_number, sku, name, status, size_variation, size, dimensions,
             description, weight_kg, cubic_volume, wood_options_note, leg_options_note,
             cushion_variation, fabric_color_count, model_abbr, manufacturer,
             default_material_cost, default_fabric_qty, default_fabric_rate,
             default_labour_hours, default_labour_persons, default_profit_pct,
             ext_cost_box, ext_cost_bubble, ext_cost_stickers, ext_cost_emboss,
             ext_cost_notecard, ext_cost_patch, ext_cost_shipping,
             ext_profit_pct, royalties_pct, vat_pct,
             fabric_manufacturer, fabric_base_code, fabric_base_link)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        num, sku, name,
        data.get("status","DRAFT"), data.get("size_variation",""), data.get("size",""),
        data.get("dimensions",""), data.get("description",""),
        data.get("weight_kg"), data.get("cubic_volume",""),
        data.get("wood_options_note",""), data.get("leg_options_note",""),
        data.get("cushion_variation",""), data.get("fabric_color_count"),
        m_abbr, data.get("manufacturer",""),
        data.get("default_material_cost"), data.get("default_fabric_qty"),
        data.get("default_fabric_rate", cfg.FABRIC_RATE_PER_METRE),
        data.get("default_labour_hours"), data.get("default_labour_persons", 1),
        data.get("default_profit_pct", cfg.PROFIT_MARGIN * 100),
        data.get("ext_cost_box", cfg.PACKAGING["box"]),
        data.get("ext_cost_bubble", cfg.PACKAGING["bubble_wrap"]),
        data.get("ext_cost_stickers", cfg.PACKAGING["stickers"]),
        data.get("ext_cost_emboss", cfg.PACKAGING["emboss_tag"]),
        data.get("ext_cost_notecard", cfg.PACKAGING["note_card"]),
        data.get("ext_cost_patch", cfg.PACKAGING["embroidery_patch"]),
        data.get("ext_cost_shipping", cfg.SHIPPING_TO_WAREHOUSE),
        data.get("ext_profit_pct", 0),
        data.get("royalties_pct", cfg.ROYALTIES_RATE * 100),
        data.get("vat_pct", cfg.VAT_RATE * 100),
        data.get("fabric_manufacturer",""), data.get("fabric_base_code",""),
        data.get("fabric_base_link",""),
    ))
    pid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone())
    row["variants"] = []
    conn.close()
    return jsonify(row), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    data = request.json or {}
    fields = ["sku","name","status","size_variation","size","dimensions","description",
              "weight_kg","cubic_volume","wood_options_note","leg_options_note",
              "cushion_variation","fabric_color_count","model_abbr","manufacturer",
              "default_material_cost","default_fabric_qty","default_fabric_rate",
              "default_labour_hours","default_labour_persons","default_profit_pct",
              "ext_cost_box","ext_cost_bubble","ext_cost_stickers","ext_cost_emboss",
              "ext_cost_notecard","ext_cost_patch","ext_cost_shipping",
              "ext_profit_pct","royalties_pct","vat_pct",
              "fabric_manufacturer","fabric_base_code","fabric_base_link"]
    updates = {k: data[k] for k in fields if k in data}

    # Auto-regenerate model_abbr uniquely when name changes and model_abbr not explicitly set
    if "name" in updates and "model_abbr" not in updates:
        conn2 = get_db()
        updates["model_abbr"] = unique_model_abbr(conn2, updates["name"], exclude_pid=pid)
        conn2.close()
    # Auto-regenerate SKU when model_abbr or name changed and SKU not explicitly set
    if ("model_abbr" in updates or "name" in updates) and "sku" not in updates:
        m = updates.get("model_abbr") or sku_gen.model_abbr(updates.get("name",""))
        if m:
            updates["sku"] = sku_gen.product_sku(m)

    updates["updated_at"] = datetime.now().isoformat()
    clause = ", ".join(f"{k}=?" for k in updates)
    conn = get_db()
    conn.execute(f"UPDATE products SET {clause} WHERE id=?", (*updates.values(), pid))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone())
    conn.close()
    return jsonify(row)


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
#  Routes — Variants
# ─────────────────────────────────────────────────────────────────

@app.route("/api/variants", methods=["POST"])
def create_variant():
    data = request.json or {}
    conn = get_db()
    bid  = data["base_product_id"]

    prod = conn.execute(
        "SELECT * FROM products WHERE id=?", (bid,)
    ).fetchone()
    pnum   = prod["product_number"]
    m_abbr = prod["model_abbr"] or sku_gen.model_abbr(prod["name"] or "")
    # Inherit product defaults when not explicitly provided
    if "material_cost"   not in data and prod["default_material_cost"]  is not None:
        data["material_cost"]   = prod["default_material_cost"]
    if "fabric_qty"      not in data and prod["default_fabric_qty"]     is not None:
        data["fabric_qty"]      = prod["default_fabric_qty"]
    if "fabric_rate"     not in data:
        data["fabric_rate"]     = prod["default_fabric_rate"] or cfg.FABRIC_RATE_PER_METRE
    if "labour_hours"    not in data and prod["default_labour_hours"]   is not None:
        data["labour_hours"]    = prod["default_labour_hours"]
    if "labour_persons"  not in data:
        data["labour_persons"]  = prod["default_labour_persons"] or 1
    if "profit_pct"      not in data:
        data["profit_pct"]      = prod["default_profit_pct"] or cfg.PROFIT_MARGIN * 100

    existing = conn.execute(
        "SELECT variant_number FROM variants WHERE base_product_id=?", (bid,)
    ).fetchall()
    subs = [int(v["variant_number"].split(".")[-1]) for v in existing if "." in v["variant_number"]]
    next_sub = max(subs) + 1 if subs else 1
    vnum = f"{pnum}.{next_sub}"

    pricing = calculate_pricing(data)

    sup         = data.get("supplier_abbr","")
    color_code  = data.get("fabric_code","")
    finish      = data.get("finish_code","")
    auto_vsku   = sku_gen.variant_sku(m_abbr, sup, color_code, finish)
    base_vsku   = data.get("variant_sku") or auto_vsku
    vsku        = unique_variant_sku(conn, base_vsku) if base_vsku else ""

    cur = conn.execute("""
        INSERT INTO variants
            (variant_number, base_product_id, variant_sku, status,
             fabric_color_name, fabric_code, fabric_type, fabric_code_link,
             wood_option, leg_option,
             material_cost, fabric_qty, fabric_cost,
             labour_hours, labour_persons, labour_cost,
             soc, profit, product_sp,
             packaging_cost, shipping_cost, external_costs,
             listed_price, royalties, listed_pre_vat, listed_with_vat,
             final_price, notes, supplier_abbr, finish_code,
             fabric_rate, profit_pct, size)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        vnum, bid,
        vsku, data.get("status","DRAFT"),
        data.get("fabric_color_name",""), color_code,
        data.get("fabric_type","PLN"), data.get("fabric_code_link",""),
        data.get("wood_option",""), data.get("leg_option",""),
        data.get("material_cost"), data.get("fabric_qty"),
        pricing.get("fabric_cost"), data.get("labour_hours"),
        data.get("labour_persons", 1), pricing.get("labour_cost"),
        pricing.get("soc"), pricing.get("profit"), pricing.get("product_sp"),
        cfg.PACKAGING_TOTAL, cfg.SHIPPING_TO_WAREHOUSE,
        pricing.get("external_costs"), pricing.get("listed_price"),
        pricing.get("royalties"), pricing.get("listed_pre_vat"),
        pricing.get("listed_with_vat"),
        data.get("final_price") or pricing.get("listed_with_vat"),
        data.get("notes",""),
        sup, finish,
        data.get("fabric_rate", cfg.FABRIC_RATE_PER_METRE),
        data.get("profit_pct", cfg.PROFIT_MARGIN * 100),
        data.get("size",""),
    ))
    vid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM variants WHERE id=?", (vid,)).fetchone())
    conn.close()
    return jsonify(row), 201


@app.route("/api/variants/<int:vid>", methods=["PUT"])
def update_variant(vid):
    data = request.json or {}
    pricing = calculate_pricing(data)

    fields = ["variant_sku","status","fabric_color_name","fabric_code","fabric_type",
              "fabric_code_link","wood_option","leg_option","material_cost","fabric_qty",
              "labour_hours","labour_persons","final_price","notes",
              "supplier_abbr","finish_code","fabric_rate","profit_pct","size"]
    updates = {k: data[k] for k in fields if k in data}
    updates.update(pricing)

    # Auto-regenerate variant_sku when SKU components change and variant_sku not explicitly set
    sku_fields = {"supplier_abbr", "fabric_code", "finish_code"}
    if sku_fields & set(data.keys()) and "variant_sku" not in data:
        conn_tmp = get_db()
        v = dict(conn_tmp.execute("SELECT * FROM variants WHERE id=?", (vid,)).fetchone())
        p = dict(conn_tmp.execute("SELECT model_abbr, name FROM products WHERE id=?",
                                  (v["base_product_id"],)).fetchone())
        conn_tmp.close()
        m = p["model_abbr"] or sku_gen.model_abbr(p["name"] or "")
        sup    = data.get("supplier_abbr") or v.get("supplier_abbr","")
        color  = data.get("fabric_code")   or v.get("fabric_code","")
        finish = data.get("finish_code")   or v.get("finish_code","")
        base = sku_gen.variant_sku(m, sup, color, finish)
        updates["variant_sku"] = unique_variant_sku(conn, base, exclude_vid=vid) if base else ""

    updates["updated_at"] = datetime.now().isoformat()

    clause = ", ".join(f"{k}=?" for k in updates)
    conn = get_db()
    conn.execute(f"UPDATE variants SET {clause} WHERE id=?", (*updates.values(), vid))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM variants WHERE id=?", (vid,)).fetchone())
    conn.close()
    return jsonify(row)


@app.route("/api/variants/<int:vid>", methods=["DELETE"])
def delete_variant(vid):
    conn = get_db()
    conn.execute("DELETE FROM variants WHERE id=?", (vid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
#  Routes — Files
# ─────────────────────────────────────────────────────────────────

@app.route("/api/files/<entity_type>/<int:eid>", methods=["GET"])
def get_files(entity_type, eid):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM files WHERE entity_type=? AND entity_id=? ORDER BY created_at",
        (entity_type, eid)
    ).fetchall()
    conn.close()
    return jsonify([{**dict(r), "url": f"/uploads/{r['filename']}"} for r in rows])


@app.route("/api/files/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return jsonify({"error": "File type not allowed (png/jpg/pdf only)"}), 400

    unique = f"{uuid.uuid4().hex}.{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    f.save(str(UPLOAD_DIR / unique))

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO files (entity_type, entity_id, file_category, filename, original_name, mime_type)
        VALUES (?,?,?,?,?,?)
    """, (
        request.form.get("entity_type","product"),
        request.form.get("entity_id"),
        request.form.get("file_category","image"),
        unique, f.filename, f.content_type
    ))
    fid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone())
    conn.close()
    return jsonify({**row, "url": f"/uploads/{unique}"}), 201


@app.route("/api/files/<int:fid>", methods=["DELETE"])
def delete_file(fid):
    conn = get_db()
    row = conn.execute("SELECT filename FROM files WHERE id=?", (fid,)).fetchone()
    if row:
        try: (UPLOAD_DIR / row["filename"]).unlink(missing_ok=True)
        except: pass
        conn.execute("DELETE FROM files WHERE id=?", (fid,))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
#  Routes — Links
# ─────────────────────────────────────────────────────────────────

@app.route("/api/links/<entity_type>/<int:eid>", methods=["GET"])
def get_links(entity_type, eid):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM links WHERE entity_type=? AND entity_id=? ORDER BY created_at",
        (entity_type, eid)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/links", methods=["POST"])
def add_link():
    data = request.json or {}
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO links (entity_type, entity_id, label, url) VALUES (?,?,?,?)",
        (data["entity_type"], data["entity_id"], data.get("label",""), data["url"])
    )
    lid = cur.lastrowid
    conn.commit()
    row = dict(conn.execute("SELECT * FROM links WHERE id=?", (lid,)).fetchone())
    conn.close()
    return jsonify(row), 201


@app.route("/api/links/<int:lid>", methods=["DELETE"])
def delete_link(lid):
    conn = get_db()
    conn.execute("DELETE FROM links WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────────────────────────
#  Routes — Shopify
# ─────────────────────────────────────────────────────────────────

@app.route("/api/shopify/validate/<int:vid>", methods=["GET"])
def validate_shopify(vid):
    conn = get_db()
    v = conn.execute("SELECT * FROM variants WHERE id=?", (vid,)).fetchone()
    if not v:
        conn.close()
        return jsonify({"valid": False, "checks": []}), 404

    p = conn.execute("SELECT * FROM products WHERE id=?", (v["base_product_id"],)).fetchone()

    imgs = conn.execute("""
        SELECT id FROM files
        WHERE mime_type LIKE 'image/%'
          AND ((entity_type='product'  AND entity_id=?)
           OR  (entity_type='variant'  AND entity_id=?))
        LIMIT 1
    """, (p["id"], vid)).fetchone()

    checks = [
        {"label": "Product name",        "pass": bool(p["name"])},
        {"label": "Product description", "pass": bool(p["description"])},
        {"label": "Product SKU",         "pass": bool(p["sku"])},
        {"label": "Fabric colour name",  "pass": bool(v["fabric_color_name"])},
        {"label": "Fabric code",         "pass": bool(v["fabric_code"])},
        {"label": "Material cost",       "pass": v["material_cost"] not in (None, 0, "")},
        {"label": "Fabric quantity",     "pass": v["fabric_qty"] not in (None, 0, "")},
        {"label": "Labour hours",        "pass": v["labour_hours"] not in (None, 0, "")},
        {"label": "Final selling price", "pass": v["final_price"] not in (None, 0, "")},
        {"label": "At least one image",  "pass": bool(imgs)},
    ]
    conn.close()
    return jsonify({"valid": all(c["pass"] for c in checks), "checks": checks})


@app.route("/api/shopify/validate-product/<int:pid>", methods=["GET"])
def validate_shopify_product(pid):
    """Validate an entire product (all variants) for Shopify readiness."""
    conn = get_db()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"valid": False, "checks": []}), 404

    variants = conn.execute(
        "SELECT * FROM variants WHERE base_product_id=?", (pid,)
    ).fetchall()
    imgs = conn.execute(
        "SELECT id FROM files WHERE entity_type='product' AND entity_id=? AND mime_type LIKE 'image/%' LIMIT 1",
        (pid,)
    ).fetchone()

    priced_variants = [v for v in variants if v["final_price"] and float(v["final_price"]) > 0]
    variants_with_sku = [v for v in variants if v["variant_sku"]]

    checks = [
        {"label": "Product name",              "pass": bool(p["name"])},
        {"label": "Product description",       "pass": bool(p["description"])},
        {"label": "Product base SKU",          "pass": bool(p["sku"])},
        {"label": "At least one variant",      "pass": len(variants) > 0},
        {"label": "All variants have a price", "pass": len(priced_variants) == len(variants) and len(variants) > 0},
        {"label": "All variants have SKUs",    "pass": len(variants_with_sku) == len(variants) and len(variants) > 0},
        {"label": "At least one image",        "pass": bool(imgs)},
        {"label": "Shopify env vars set",      "pass": bool(os.environ.get("SHOPIFY_SHOP_URL")) and bool(os.environ.get("SHOPIFY_ACCESS_TOKEN"))},
    ]
    variant_issues = []
    for v in variants:
        issues = []
        if not v["fabric_color_name"]: issues.append("missing colour name")
        if not v["final_price"] or float(v["final_price"] or 0) == 0: issues.append("no price")
        if not v["variant_sku"]: issues.append("no SKU")
        if issues:
            variant_issues.append({"variant_number": v["variant_number"], "issues": issues})

    conn.close()
    return jsonify({
        "valid": all(c["pass"] for c in checks),
        "checks": checks,
        "variant_issues": variant_issues,
        "shopify_product_id": p["shopify_product_id"],
    })


def _shopify_upload_image(base, headers, spid, filepath, alt=""):
    """Upload a local image file to a Shopify product via multipart. Returns attachment payload."""
    import base64 as b64
    try:
        with open(filepath, "rb") as f:
            data = b64.b64encode(f.read()).decode()
        ext = Path(filepath).suffix.lstrip(".").lower()
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
        return {"attachment": data, "filename": Path(filepath).name,
                "content_type": mime_map.get(ext, "image/jpeg"), "alt": alt}
    except Exception:
        return None


def _shopify_set_metafields(base, headers, spid, svid, variant_row, product_row):
    """Push cost breakdown as Shopify metafields on the variant (private, not customer-visible)."""
    import requests as req
    mf_product = [
        {"namespace": "couch_petato", "key": "sku",           "value": product_row["sku"] or "",     "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "model_abbr",    "value": product_row["model_abbr"] or "","type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "manufacturer",  "value": product_row["manufacturer"] or "","type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "weight_kg",     "value": str(product_row["weight_kg"] or ""),"type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "cubic_volume",  "value": str(product_row["cubic_volume"] or ""),"type": "single_line_text_field"},
    ]
    mf_variant = [
        {"namespace": "couch_petato", "key": "variant_sku",   "value": variant_row["variant_sku"] or "",  "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "size",          "value": variant_row["size"] or "",          "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "wood_option",   "value": variant_row["wood_option"] or "",   "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "fabric_code",   "value": variant_row["fabric_code"] or "",   "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "material_cost", "value": str(variant_row["material_cost"] or 0), "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "fabric_qty",    "value": str(variant_row["fabric_qty"] or 0),    "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "fabric_cost",   "value": str(variant_row["fabric_cost"] or 0),   "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "labour_hours",  "value": str(variant_row["labour_hours"] or 0),  "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "labour_cost",   "value": str(variant_row["labour_cost"] or 0),   "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "soc",           "value": str(variant_row["soc"] or 0),           "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "profit_pct",    "value": str(variant_row["profit_pct"] or 0),    "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "packaging_cost","value": str(variant_row["packaging_cost"] or 0),"type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "shipping_cost", "value": str(variant_row["shipping_cost"] or 0), "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "listed_price",  "value": str(variant_row["listed_price"] or 0),  "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "final_price",   "value": str(variant_row["final_price"] or 0),   "type": "single_line_text_field"},
        {"namespace": "couch_petato", "key": "notes",         "value": variant_row["notes"] or "",             "type": "single_line_text_field"},
    ]
    # Product metafields
    for mf in mf_product:
        req.post(f"{base}/products/{spid}/metafields.json",
                 json={"metafield": mf}, headers=headers, timeout=10)
    # Variant metafields
    for mf in mf_variant:
        req.post(f"{base}/products/{spid}/variants/{svid}/metafields.json",
                 json={"metafield": mf}, headers=headers, timeout=10)


def _shopify_get_location_id(base, headers):
    """Return the first active Shopify location ID, or None on failure."""
    import requests as req
    try:
        r = req.get(f"{base}/locations.json", headers=headers, timeout=15)
        locs = r.json().get("locations", []) if r.ok else []
        active = [l for l in locs if l.get("active")]
        return active[0]["id"] if active else (locs[0]["id"] if locs else None)
    except Exception as e:
        print(f"[Shopify] Location fetch error: {e}")
        return None


def _shopify_set_inventory_level(base, headers, location_id, inventory_item_id, available):
    """Set Shopify inventory level for a variant at a location. Returns True on success."""
    import requests as req
    try:
        r = req.post(
            f"{base}/inventory_levels/set.json",
            json={"location_id": location_id,
                  "inventory_item_id": inventory_item_id,
                  "available": int(available)},
            headers=headers, timeout=15
        )
        return r.ok
    except Exception as e:
        print(f"[Shopify] Inventory set error: {e}")
        return False


def _compute_variant_units(conn, pid, fabric_color_name, fabric_qty):
    """
    Calculate how many units of a variant can be sold based on fabric stock.
    Looks up the fabric option matching fabric_color_name on product pid.
    Returns available_units (int, may be 0) and a dict of stock info.
    """
    import math
    if not fabric_color_name or not fabric_qty or fabric_qty <= 0:
        return 0, {}
    row = conn.execute(
        "SELECT stock_metres, stock_status FROM product_options "
        "WHERE product_id=? AND option_type='fabric' AND value=? LIMIT 1",
        (pid, fabric_color_name)
    ).fetchone()
    if not row:
        return 0, {}
    metres  = row["stock_metres"]
    status  = row["stock_status"]
    if status != "in_stock" or metres is None or metres < 30:
        return 0, {"stock_metres": metres, "stock_status": status}
    units = math.floor(metres / fabric_qty)
    return units, {"stock_metres": metres, "stock_status": status, "units": units}


@app.route("/api/shopify/push/<int:pid>/all", methods=["POST"])
def push_shopify_product(pid):
    """
    Push an entire product + ALL its variants to Shopify.
    - Creates or updates the Shopify product record.
    - Upserts every variant as a proper Shopify variant (options: Size, Fabric, Wood).
    - Uploads product images from local storage.
    - Writes cost breakdown to Shopify metafields (private).
    """
    import requests as req

    shop_url   = os.environ.get("SHOPIFY_SHOP_URL", "")
    shop_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not shop_url or not shop_token:
        return jsonify({"error": "Set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN env vars first."}), 400

    conn    = get_db()
    p       = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    variants = conn.execute(
        "SELECT * FROM variants WHERE base_product_id=? ORDER BY variant_number", (pid,)
    ).fetchall()
    imgs = conn.execute(
        "SELECT * FROM files WHERE entity_type='product' AND entity_id=? AND mime_type LIKE 'image/%' ORDER BY created_at",
        (pid,)
    ).fetchall()

    headers = {"X-Shopify-Access-Token": shop_token, "Content-Type": "application/json"}
    base    = f"https://{shop_url}/admin/api/{cfg.SHOPIFY_API_VERSION}"

    # ── Build variant option values ──────────────────────────────────
    sizes   = list(dict.fromkeys(v["size"]          or "Default" for v in variants))
    colours = list(dict.fromkeys(v["fabric_color_name"] or "Default" for v in variants))
    woods   = list(dict.fromkeys(v["wood_option"]   or "Standard" for v in variants))

    options = [
        {"name": "Size",   "values": sizes},
        {"name": "Colour", "values": colours},
        {"name": "Wood",   "values": woods},
    ]
    # Flatten to Shopify variant list
    shopify_variants = []
    for v in variants:
        sv = {
            "option1":      v["size"]              or "Default",
            "option2":      v["fabric_color_name"] or "Default",
            "option3":      v["wood_option"]       or "Standard",
            "sku":          v["variant_sku"]        or p["sku"],
            "price":        str(v["final_price"]    or 0),
            "weight":       float(p["weight_kg"]    or 0),
            "weight_unit":  "kg",
            "requires_shipping": True,
            "taxable":      True,
            "inventory_management": "shopify",
            "inventory_policy":     "deny",
            "fulfillment_service":  "manual",
        }
        shopify_variants.append(sv)

    # ── Image payloads (base64 upload) ───────────────────────────────
    image_payloads = []
    for img in imgs:
        fp = UPLOAD_DIR / img["filename"]
        payload = _shopify_upload_image(base, headers, None, str(fp), alt=p["name"])
        if payload:
            image_payloads.append(payload)

    now = datetime.now().isoformat()
    # Get Shopify location once (needed for inventory level set calls)
    location_id = _shopify_get_location_id(base, headers)
    if not location_id:
        print("[Shopify] Warning: could not fetch location ID — inventory quantities will not be set")

    if p["shopify_product_id"]:
        # ── UPDATE existing Shopify product ──────────────────────────
        spid_str = p["shopify_product_id"]
        update_payload = {"product": {
            "id":        spid_str,
            "title":     p["name"],
            "body_html": p["description"] or "",
            "vendor":    "Couch Petato",
            "product_type": "Pet Furniture",
            "options":   options,
        }}
        r = req.put(f"{base}/products/{spid_str}.json", json=update_payload,
                    headers=headers, timeout=30)
        if r.status_code not in (200, 201):
            conn.close()
            return jsonify({"error": f"Product update failed: {r.text}"}), r.status_code

        spid = spid_str

        # Get existing Shopify variants so we can match / upsert
        existing_sv_resp = req.get(f"{base}/products/{spid}/variants.json",
                                   headers=headers, timeout=15)
        existing_svs = existing_sv_resp.json().get("variants", []) if existing_sv_resp.ok else []
        # Build lookup: (opt1,opt2,opt3) → shopify variant id
        existing_map = {
            (sv.get("option1",""), sv.get("option2",""), sv.get("option3","")): sv["id"]
            for sv in existing_svs
        }

        synced = []
        for v, sv_payload in zip(variants, shopify_variants):
            key = (sv_payload["option1"], sv_payload["option2"], sv_payload["option3"])
            existing_id = v["shopify_variant_id"] or existing_map.get(key)
            if existing_id:
                sv_payload["id"] = existing_id
                r2 = req.put(f"{base}/products/{spid}/variants/{existing_id}.json",
                             json={"variant": sv_payload}, headers=headers, timeout=15)
                if r2.ok:
                    svid = existing_id
                    sv_data = r2.json().get("variant", {})
                    inv_item_id = sv_data.get("inventory_item_id") or v["shopify_inventory_item_id"]
                    units, _ = _compute_variant_units(conn, pid, v["fabric_color_name"], v["fabric_qty"])
                    if inv_item_id and location_id:
                        _shopify_set_inventory_level(base, headers, location_id, inv_item_id, units)
                    _shopify_set_metafields(base, headers, spid, svid, dict(v), dict(p))
                    conn.execute(
                        "UPDATE variants SET shopify_variant_id=?, shopify_inventory_item_id=?, shopify_synced_at=? WHERE id=?",
                        (svid, inv_item_id, now, v["id"]))
                    synced.append({"local_id": v["id"], "shopify_variant_id": svid,
                                   "action": "updated", "units_set": units})
            else:
                r2 = req.post(f"{base}/products/{spid}/variants.json",
                              json={"variant": sv_payload}, headers=headers, timeout=15)
                if r2.ok:
                    sv_data = r2.json().get("variant", {})
                    svid = sv_data.get("id")
                    inv_item_id = sv_data.get("inventory_item_id")
                    if svid:
                        units, _ = _compute_variant_units(conn, pid, v["fabric_color_name"], v["fabric_qty"])
                        if inv_item_id and location_id:
                            _shopify_set_inventory_level(base, headers, location_id, inv_item_id, units)
                        _shopify_set_metafields(base, headers, spid, svid, dict(v), dict(p))
                        conn.execute(
                            "UPDATE variants SET shopify_variant_id=?, shopify_inventory_item_id=?, shopify_synced_at=? WHERE id=?",
                            (svid, inv_item_id, now, v["id"]))
                        synced.append({"local_id": v["id"], "shopify_variant_id": svid,
                                       "action": "created", "units_set": units})

        # Upload new images
        for img_p in image_payloads:
            req.post(f"{base}/products/{spid}/images.json",
                     json={"image": img_p}, headers=headers, timeout=30)

        conn.execute("UPDATE products SET shopify_product_id=?, updated_at=? WHERE id=?",
                     (spid, now, pid))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "shopify_product_id": spid, "variants_synced": synced})

    else:
        # ── CREATE new Shopify product ────────────────────────────────
        product_payload = {"product": {
            "title":        p["name"],
            "body_html":    p["description"] or "",
            "vendor":       "Couch Petato",
            "product_type": "Pet Furniture",
            "status":       "draft",
            "options":      options,
            "variants":     shopify_variants,
            "images":       image_payloads,
        }}
        r = req.post(f"{base}/products.json", json=product_payload,
                     headers=headers, timeout=60)
        if r.status_code not in (200, 201):
            conn.close()
            return jsonify({"error": f"Product create failed: {r.text}"}), r.status_code

        rd   = r.json().get("product", {})
        spid = rd.get("id")
        shopify_vars = rd.get("variants", [])

        conn.execute("UPDATE products SET shopify_product_id=?, updated_at=? WHERE id=?",
                     (spid, now, pid))

        synced = []
        for v, sv in zip(variants, shopify_vars):
            svid = sv.get("id")
            inv_item_id = sv.get("inventory_item_id")
            if svid:
                units, _ = _compute_variant_units(conn, pid, v["fabric_color_name"], v["fabric_qty"])
                if inv_item_id and location_id:
                    _shopify_set_inventory_level(base, headers, location_id, inv_item_id, units)
                _shopify_set_metafields(base, headers, spid, svid, dict(v), dict(p))
                conn.execute(
                    "UPDATE variants SET shopify_variant_id=?, shopify_inventory_item_id=?, shopify_synced_at=? WHERE id=?",
                    (svid, inv_item_id, now, v["id"]))
                synced.append({"local_id": v["id"], "shopify_variant_id": svid,
                               "action": "created", "units_set": units})

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "shopify_product_id": spid, "variants_synced": synced})


@app.route("/api/warwick/test-login", methods=["POST"])
def warwick_test_login():
    """Force a fresh Warwick login and report success/failure."""
    _reset_warwick_session()
    session = _get_warwick_session()
    if session:
        email = os.environ.get("WARWICK_EMAIL", "")
        return jsonify({"ok": True, "message": f"Logged in as {email}"})
    email = os.environ.get("WARWICK_EMAIL", "").strip()
    if not email or email == "your@email.com":
        return jsonify({"ok": False, "message": "Credentials not set. Edit .env file and restart the server."})
    return jsonify({"ok": False, "message": "Login failed — check your email/password in .env"})


@app.route("/api/fabric/refresh-stock/<int:option_id>", methods=["POST"])
def refresh_fabric_stock(option_id):
    """Immediately scrape stock for a single fabric option and return result."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, product_id, value, link, supplier FROM product_options WHERE id=? AND option_type='fabric'",
        (option_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Fabric option not found"}), 404

    if not row["link"]:
        return jsonify({"error": "No link saved for this fabric — add one first"}), 400

    metres, status = scrape_fabric_stock(row["link"], row["supplier"] or "")
    now = datetime.now().isoformat()

    conn2 = get_db()
    conn2.execute(
        "UPDATE product_options SET stock_metres=?, stock_status=?, stock_updated_at=? WHERE id=?",
        (metres, status, now, option_id)
    )
    conn2.commit()
    conn2.close()

    # Auto-update Shopify inventory for all variants using this fabric (background, silent)
    import threading
    threading.Thread(
        target=_sync_inventory_for_fabric,
        args=(row["value"], row["product_id"]),
        daemon=True
    ).start()

    return jsonify({
        "ok": True,
        "id": option_id,
        "stock_metres": metres,
        "stock_status": status,
        "stock_updated_at": now,
    })


@app.route("/api/shopify/push/<int:vid>", methods=["POST"])
def push_shopify(vid):
    """Legacy single-variant push — redirects to the full product push."""
    conn = get_db()
    v = conn.execute("SELECT base_product_id FROM variants WHERE id=?", (vid,)).fetchone()
    conn.close()
    if not v:
        return jsonify({"error": "Variant not found"}), 404
    # Delegate to full product push
    with app.test_request_context():
        pass
    import requests as req
    shop_url   = os.environ.get("SHOPIFY_SHOP_URL", "")
    shop_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not shop_url or not shop_token:
        return jsonify({"error": "Set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN environment variables first."}), 400
    # Call internal push endpoint
    from flask import url_for
    pid = v["base_product_id"]
    return push_shopify_product(pid)


@app.route("/api/shopify/sync-inventory/<int:pid>", methods=["POST"])
def sync_shopify_inventory(pid):
    """
    Sync Shopify inventory quantities for all variants of a product
    without re-pushing product data.
    Reads current fabric stock from product_options and sets
    inventory_level = floor(stock_metres / fabric_qty) per variant.
    """
    import requests as req
    import math

    shop_url   = os.environ.get("SHOPIFY_SHOP_URL", "")
    shop_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not shop_url or not shop_token:
        return jsonify({"error": "Shopify credentials not configured"}), 400

    headers = {"X-Shopify-Access-Token": shop_token, "Content-Type": "application/json"}
    base    = f"https://{shop_url}/admin/api/{cfg.SHOPIFY_API_VERSION}"

    conn = get_db()
    p    = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p or not p["shopify_product_id"]:
        conn.close()
        return jsonify({"error": "Product not found or not yet pushed to Shopify"}), 404

    variants = conn.execute(
        "SELECT * FROM variants WHERE base_product_id=? AND shopify_variant_id IS NOT NULL",
        (pid,)
    ).fetchall()
    if not variants:
        conn.close()
        return jsonify({"ok": True, "message": "No Shopify-synced variants found", "updated": []})

    location_id = _shopify_get_location_id(base, headers)
    if not location_id:
        conn.close()
        return jsonify({"error": "Could not fetch Shopify location ID"}), 500

    updated = []
    for v in variants:
        svid        = v["shopify_variant_id"]
        inv_item_id = v["shopify_inventory_item_id"]

        # If inventory_item_id not stored locally, fetch from Shopify
        if not inv_item_id:
            try:
                r = req.get(f"{base}/variants/{svid}.json", headers=headers, timeout=10)
                if r.ok:
                    inv_item_id = r.json().get("variant", {}).get("inventory_item_id")
                    if inv_item_id:
                        conn.execute(
                            "UPDATE variants SET shopify_inventory_item_id=? WHERE id=?",
                            (inv_item_id, v["id"]))
            except Exception:
                pass

        if not inv_item_id:
            updated.append({"local_id": v["id"], "shopify_variant_id": svid,
                             "error": "inventory_item_id unknown — push product first"})
            continue

        units, info = _compute_variant_units(conn, pid, v["fabric_color_name"], v["fabric_qty"])
        ok = _shopify_set_inventory_level(base, headers, location_id, inv_item_id, units)
        updated.append({
            "local_id": v["id"],
            "shopify_variant_id": svid,
            "fabric": v["fabric_color_name"],
            "units_set": units,
            "stock_info": info,
            "ok": ok,
        })

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "product_id": pid, "shopify_product_id": p["shopify_product_id"],
                    "location_id": location_id, "updated": updated})


def _sync_inventory_for_fabric(fabric_name, product_id):
    """
    Called after a fabric stock update — pushes new inventory quantities to Shopify
    for all variants that use this fabric on this product (if already synced).
    Runs silently (logs errors, does not raise).
    """
    import requests as req

    shop_url   = os.environ.get("SHOPIFY_SHOP_URL", "")
    shop_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not shop_url or not shop_token:
        return  # Shopify not configured yet — skip silently

    headers = {"X-Shopify-Access-Token": shop_token, "Content-Type": "application/json"}
    base    = f"https://{shop_url}/admin/api/{cfg.SHOPIFY_API_VERSION}"

    try:
        conn = get_db()
        variants = conn.execute(
            "SELECT * FROM variants WHERE base_product_id=? AND fabric_color_name=? "
            "AND shopify_variant_id IS NOT NULL",
            (product_id, fabric_name)
        ).fetchall()
        if not variants:
            conn.close()
            return

        location_id = _shopify_get_location_id(base, headers)
        if not location_id:
            conn.close()
            return

        for v in variants:
            inv_item_id = v["shopify_inventory_item_id"]
            if not inv_item_id:
                r = req.get(f"{base}/variants/{v['shopify_variant_id']}.json", headers=headers, timeout=10)
                if r.ok:
                    inv_item_id = r.json().get("variant", {}).get("inventory_item_id")
                    if inv_item_id:
                        conn.execute("UPDATE variants SET shopify_inventory_item_id=? WHERE id=?",
                                     (inv_item_id, v["id"]))
            if inv_item_id:
                units, _ = _compute_variant_units(conn, product_id, fabric_name, v["fabric_qty"])
                _shopify_set_inventory_level(base, headers, location_id, inv_item_id, units)
                print(f"[Shopify] Inventory updated: variant {v['id']} → {units} units")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Shopify] Auto inventory sync error for fabric '{fabric_name}': {e}")


# ─────────────────────────────────────────────────────────────────
#  Stock Scraping
# ─────────────────────────────────────────────────────────────────

# ── Warwick session cache ──────────────────────────────────────────
_warwick_session   = None   # requests.Session, reused across calls
_warwick_logged_in = False  # True once we've authenticated this run

WARWICK_LOGIN_URL = "https://www.warwick.com.au/account/login/"
WARWICK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def _get_warwick_session():
    """Return an authenticated requests.Session for warwick.com.au.
    Reads WARWICK_EMAIL / WARWICK_PASSWORD from environment (.env file).
    Returns None if credentials are missing or login fails.
    """
    global _warwick_session, _warwick_logged_in
    try:
        import requests as _req
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    email    = os.environ.get("WARWICK_EMAIL", "").strip()
    password = os.environ.get("WARWICK_PASSWORD", "").strip()
    if not email or not password or email == "your@email.com":
        print("[Warwick] Credentials not set — edit .env and set WARWICK_EMAIL / WARWICK_PASSWORD")
        return None

    # Re-use cached session if already logged in
    if _warwick_session and _warwick_logged_in:
        return _warwick_session

    session = _req.Session()
    session.headers.update({"User-Agent": WARWICK_UA})

    try:
        # 1. GET the login page to collect the CSRF token
        r = session.get(WARWICK_LOGIN_URL, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
        csrf_token = csrf_input["value"] if csrf_input else ""

        # 2. POST credentials
        payload = {
            "csrfmiddlewaretoken": csrf_token,
            "login":               email,
            "password":            password,
            "remember":            "on",
        }
        headers = {
            "Referer":    WARWICK_LOGIN_URL,
            "Origin":     "https://www.warwick.com.au",
        }
        resp = session.post(WARWICK_LOGIN_URL, data=payload, headers=headers,
                            timeout=15, allow_redirects=True)

        # Check if login succeeded: logged-in pages typically contain the user's
        # account info and NOT the login form.
        page_text = resp.text.lower()
        if "my account" in page_text or "sign out" in page_text or "logout" in page_text:
            print("[Warwick] Login successful")
            _warwick_session   = session
            _warwick_logged_in = True
            return session
        else:
            print("[Warwick] Login failed — check credentials in .env")
            _warwick_session   = None
            _warwick_logged_in = False
            return None

    except Exception as exc:
        print(f"[Warwick] Login error: {exc}")
        return None


def _reset_warwick_session():
    """Force re-login on next call (e.g. after a 403 / session expiry)."""
    global _warwick_session, _warwick_logged_in
    _warwick_session   = None
    _warwick_logged_in = False


def scrape_fabric_stock(url, supplier_name=""):
    """
    Fetch a fabric supplier page and extract available stock in metres.
    For Warwick: logs in first, then looks for Dubai / Somerton warehouse qtys (threshold 30m).
    Returns (stock_metres, stock_status) where status is 'in_stock'/'no_stock'/'unknown'.
    """
    try:
        import requests as _req
        from bs4 import BeautifulSoup
    except ImportError:
        return None, "unknown"

    if not url or not url.startswith("http"):
        return None, "unknown"

    import re
    threshold  = 30  # metres
    sup_lower  = (supplier_name or "").lower()
    is_warwick = "warwick" in sup_lower

    def _fetch(session_or_none):
        hdrs = {"User-Agent": WARWICK_UA}
        if session_or_none:
            return session_or_none.get(url, timeout=15)
        return _req.get(url, headers=hdrs, timeout=15)

    try:
        if is_warwick:
            session = _get_warwick_session()
            resp = _fetch(session)
            # If we get a redirect to login (session expired), force re-login and retry once
            if resp and resp.url and "login" in resp.url:
                _reset_warwick_session()
                session = _get_warwick_session()
                resp = _fetch(session)
        else:
            resp = _fetch(None)

        if not resp:
            return None, "unknown"
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        if is_warwick:
            best_qty = None

            # Strategy 1: scan <table> rows for Dubai / Somerton cells
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if not cells:
                        continue
                    row_txt = " ".join(cells).lower()
                    if "dubai" in row_txt or "somerton" in row_txt:
                        nums = re.findall(r"(\d+(?:\.\d+)?)", row_txt)
                        for n in nums:
                            qty = float(n)
                            if 0 < qty < 50000:
                                best_qty = max(best_qty or 0, qty)

            # Strategy 2: plain-text pattern (location name → nearby number)
            if best_qty is None:
                for loc in ("dubai", "somerton"):
                    pattern = (
                        rf"(?i){loc}"
                        rf"[^0-9]{{0,150}}"
                        rf"(\d{{1,5}}(?:\.\d+)?)"
                        rf"\s*(?:m\b|lm\b|metres?|meters?)?"
                    )
                    for m in re.finditer(pattern, text):
                        qty = float(m.group(1))
                        if 0 < qty < 50000:
                            best_qty = max(best_qty or 0, qty)

            if best_qty is not None:
                status = "in_stock" if best_qty >= threshold else "no_stock"
                return best_qty, status

            # If logged in but found nothing, return unknown rather than false negative
            if is_warwick and session:
                return None, "unknown"

        else:
            # Generic supplier: find metres on page
            qty_pattern = (
                r"(\d{1,5}(?:\.\d+)?)"
                r"\s*(?:m\b|lm\b|linear\s*m(?:etr[eo]s?)?\b|metres?\b|meters?\b)"
            )
            nums = [float(m) for m in re.findall(qty_pattern, text, re.IGNORECASE)
                    if 0 < float(m) < 50000]
            if nums:
                best_qty = max(nums)
                status = "in_stock" if best_qty >= threshold else "no_stock"
                return best_qty, status

        # Text-based fallback
        lower = text.lower()
        if "out of stock" in lower or "no stock" in lower or "unavailable" in lower:
            return 0.0, "no_stock"
        if "in stock" in lower or "available" in lower:
            return None, "in_stock"
        return None, "unknown"

    except Exception as exc:
        print(f"[Stock] Error scraping {url}: {exc}")
        return None, "unknown"


def update_fabric_stocks():
    """Called by the scheduler — updates every fabric option that has a link,
    then pushes updated inventory quantities to Shopify for all affected variants."""
    print(f"[Stock] Running scheduled update at {datetime.now().isoformat()}")
    conn = get_db()
    rows = conn.execute(
        "SELECT id, product_id, value, link, supplier FROM product_options "
        "WHERE option_type='fabric' AND link IS NOT NULL AND link != ''"
    ).fetchall()
    conn.close()

    updated = 0
    for row in rows:
        metres, status = scrape_fabric_stock(row["link"], row["supplier"] or "")
        now = datetime.now().isoformat()
        c2 = get_db()
        c2.execute(
            "UPDATE product_options SET stock_metres=?, stock_status=?, stock_updated_at=? WHERE id=?",
            (metres, status, now, row["id"])
        )
        c2.commit()
        c2.close()
        updated += 1
        # Push updated inventory count to Shopify for variants using this fabric
        _sync_inventory_for_fabric(row["value"], row["product_id"])

    print(f"[Stock] Updated {updated} fabric option(s) and synced Shopify inventory.")


def _start_scheduler():
    """Start APScheduler for twice-daily stock scraping (06:00 + 18:00 Asia/Dubai)."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = BackgroundScheduler(timezone="Asia/Dubai")
        scheduler.add_job(update_fabric_stocks, CronTrigger(hour=6,  minute=0))
        scheduler.add_job(update_fabric_stocks, CronTrigger(hour=18, minute=0))
        scheduler.start()
        print("[Scheduler] Stock refresh scheduled at 06:00 and 18:00 Asia/Dubai")
    except ImportError:
        print("[Scheduler] APScheduler not installed — stock auto-refresh disabled.")
    except Exception as exc:
        print(f"[Scheduler] Could not start: {exc}")


# ─────────────────────────────────────────────────────────────────
#  Start
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    # Start scheduler only in the actual server process (not the Werkzeug reloader watcher)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        _start_scheduler()
    print("\n  Couch Petato — Product Manager")
    print("  http://localhost:5001\n")
    app.run(debug=True, port=5001, threaded=True)
