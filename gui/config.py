# ─────────────────────────────────────────────
#  Couch Petato — Pricing & Platform Config
#  All prices in AED. Edit here, never in code.
# ─────────────────────────────────────────────

# Fabric
FABRIC_RATE_PER_METRE = 50        # AED per metre (plain fabric)

# Labour (Symphony Interiors)
LABOUR_RATE_PER_PERSON_HOUR = 20  # AED

# Margin
PROFIT_MARGIN = 0.60              # 60% on top of SOC

# Platform fees (Shopify 2% + Stripe 3% + 3D Configurator 2%)
ROYALTIES_RATE = 0.07             # 7%

# UAE VAT
VAT_RATE = 0.05                   # 5%

# Packaging (AED)
PACKAGING = {
    "box":               30,
    "bubble_wrap":       10,
    "stickers":          15,
    "emboss_tag":        20,
    "note_card":         20,
    "embroidery_patch":  20,
}
PACKAGING_TOTAL = sum(PACKAGING.values())  # 115 AED

# Shipping
SHIPPING_TO_WAREHOUSE = 100       # AED internal
SHIPPING_TO_CUSTOMER = 50         # AED UAE flat rate

# ─── Shopify (set as env vars, not here) ───
# SHOPIFY_SHOP_URL      e.g.  your-store.myshopify.com
# SHOPIFY_ACCESS_TOKEN  Admin API token
SHOPIFY_API_VERSION = "2024-01"
