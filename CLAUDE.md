# Couch Petato — Claude Code Project Brief

## Business Overview
Pet furniture brand based in the UAE. Products are handmade in-house. Sales channels are social media (Instagram: @couch.petato) and a website with a 3D configurator that allows clients to customise material and colour, driving dynamic pricing. The brand may scale into regular furniture.

**Currency:** AED (UAE Dirham)  
**Shipping cost (UAE):** 50 AED flat  
**Platform fees to account for:** Shopify 2%, 3D configurator 2%, Stripe 3% — treat as ~10% total + 5% UAE VAT

---

## Tech Stack
- **E-commerce:** Shopify (Storefront + Admin API)
- **3D Configurator:** Integrated on the website for live material/colour selection
- **Database:** To be built on top of the existing Excel pricing model
- **Language preference:** JavaScript/Node.js preferred for Shopify scripts; Python acceptable for data/DB work

---

## Product Catalogue (Current)
| # | Name | SKU | Description |
|---|------|-----|-------------|
| 1 | Cami Round | CP619SI | Round wooden piece, veneer inside/outside, Mickey Mouse ear legs, 2 cushion configs |
| 2 | Reacher Box | TBD | Curved box, fabric-wrapped |
| 3 | Lisa Round | TBD | Round, no cushion |
| 4 | Coco Seater | TBD | Single seater |
| 5 | Acrylic Box | TBD | Acrylic construction |

---

## SKU System

### Format
```
CP - [3-digit product number] - [2-letter material/supplier code]
```
Example: `CP619SI` = Couch Petato | product #619 | Symphony Interiors

### SKU Logic
- The SKU identifies the **skeleton/frame only** — the base product regardless of fabric or colour.
- Each fabric + colour combination creates a **variant**, not a new SKU.
- Variants are tracked as `[BASE-SKU]-[FABRIC-CODE]-[COLOR-CODE]`  
  Example: `CP619SI-PLN-BEI` = Cami Round, plain fabric, beige

### Material/Supplier Codes
| Code | Meaning |
|------|---------|
| SI | Symphony Interiors (upholstery supplier) |

### Fabric Type Codes
| Code | Type |
|------|------|
| PLN | Plain / simple texture |
| PAT | Pattern / premium |

---

## Pricing Model

Pricing is calculated per skeleton, then variants adjust based on fabric selection. All figures in AED.

### Cost Components
| Component | Notes |
|-----------|-------|
| Wood cost | Base material cost for the frame |
| SI stock charge | Wood cost + 20% (Symphony Interiors markup) |
| Fabric qty (plain) | Metres × 40 AED/m |
| Fabric qty (pattern) | Metres × rate (premium) |
| Upholstery labour | Hours × 200 AED/hr (Symphony Interiors) |
| SOC (Sum of Costs) | Wood + Fabric + Labour |
| Packaging | Box (30) + Bubble wrap (10) + Stickers (15) + Emboss tag (20) + Note card (20) + Embroidery patch (20) |
| Shipping | 100 AED internal; 50 AED to customer |

### Pricing Formula
```
SOC = Wood cost + Fabric cost + Upholstery cost
External costs = Packaging items + Shipping
Pre-final = SOC × 75% markup
Final (before fees) = Pre-final + 12%
Selling price = Final + 65% profit margin
Platform loss = 15% of selling price (Shopify + 3D + Stripe + VAT)
Final SP = Selling price + platform loss
```

### Dynamic Pricing (3D Configurator)
Each material/colour option has its own cost. The configurator calculates the final price live based on:
- Selected wood stain (3 solid stains or 3 readymade/cheaper options)
- Selected leg option (5 leg types)
- Selected fabric (10 plain or 2 pattern premium)
- Selected colour

Wood options: 3 solid wood stains + 3 readymade (cheaper)  
Leg options: 5 types  
Fabric: 10 plain/simple texture + 2 pattern premium  

---

## Database Requirements

The database is built on top of the Excel pricing model. Key entities:

### Products table
- `sku` (base SKU, e.g. CP619SI)
- `name`
- `description`
- `weight_kg`
- `cubic_volume`
- `wood_cost`
- `upholstery_hours`
- `upholstery_cost`
- `packaging_cost`

### Variants table
- `variant_sku` (e.g. CP619SI-PLN-BEI)
- `base_sku` (FK to Products)
- `fabric_type` (plain | pattern)
- `fabric_colour`
- `wood_option`
- `leg_option`
- `fabric_qty_metres`
- `fabric_cost`
- `calculated_price`

### Materials / Options tables
- Wood options with costs
- Leg options with costs
- Fabric colours with costs per metre

---

## Shopify Setup Notes
- Products in Shopify map to base SKUs
- Variants in Shopify map to fabric+colour combinations
- Metafields should be used to store cost breakdowns per variant (not visible to customers)
- The 3D configurator hooks into the Shopify cart via the Storefront API

---

## File Structure (Target)
```
/
├── CLAUDE.md               ← this file
├── shopify/
│   ├── theme/              ← theme customisations
│   ├── scripts/            ← Admin API scripts (product sync, pricing)
│   └── storefront/         ← Storefront API / configurator integration
├── database/
│   ├── schema.sql          ← or schema.prisma
│   ├── seed/               ← seed data from Excel
│   └── migrations/
├── pricing/
│   ├── calculator.js       ← pricing logic as reusable module
│   └── sku-generator.js    ← SKU generation utilities
└── data/
    └── pricing-master.xlsx ← source of truth for costs
```

---

## Key Conventions
- All prices in AED, stored as floats with 2 decimal places
- SKUs are always uppercase
- Variant SKUs use hyphens as separators
- Never hardcode platform fee percentages — keep them in a config file
- Commit pricing changes with a note on what cost changed and why
