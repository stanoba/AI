---
name: tme-search
description: Search electronic components, check live stock & pricing, fetch PDF datasheets, and manage project favorites on TME.eu webshop using TME API. Activate when searching for hardware components, microcontrollers, MOSFETs, LEDs, connectors, passive components, or checking component availability for schematics and PCB designs.
---

# TME.eu Component Search & Stock Checker Skill

This skill allows the agent to search for electronic components on [TME.eu](https://www.tme.eu), inspect live stock levels and volume pricing, fetch component datasheets, and maintain a local favorites list (`tme_favorites.json`) for the project.

## Quick Usage & CLI Commands

All interactions are executed via the helper script located at `.agents/skills/tme-search/scripts/tme_cli.py`.

### 1. Search Components
Search the TME catalog for components matching a keyword or spec (e.g. MOSFETs, microcontrollers, resistors):
```bash
python .agents/skills/tme-search/scripts/tme_cli.py search "<QUERY>" [--in-stock] [--limit 10] [--json]
```
- Example: `python .agents/skills/tme-search/scripts/tme_cli.py search "MOSFET N-CH SOT23" --in-stock --limit 5`

### 2. Get Component Details & Datasheet URLs
Retrieve detailed parameters, EAN, MOQ, and direct PDF datasheet links for given TME symbols:
```bash
python .agents/skills/tme-search/scripts/tme_cli.py details <SYMBOL1> [<SYMBOL2> ...]
```
- Example: `python .agents/skills/tme-search/scripts/tme_cli.py details 2N7002-DIO WS2812B`

### 3. Manage Project Favorites & BOM Parts List
Add components to the local project parts list (`tme_favorites.json`) and check live stock/prices across all favorited components:
- **Add to favorites**:
  ```bash
  python .agents/skills/tme-search/scripts/tme_cli.py favorite add <SYMBOL> --role "<DESIGNATED_ROLE>"
  ```
- **List & Check Stock for Favorites**:
  ```bash
  python .agents/skills/tme-search/scripts/tme_cli.py favorite list
  ```

---

## Configuration & Credentials

The API Token and Secret are loaded automatically from `.agents/skills/tme-search/.env` or the project root `.env`:

```env
TME_TOKEN=your_tme_token_50_chars_placeholder_xyz1234567890
TME_SECRET=your_tme_secret_20_chars_1234
TME_COUNTRY=SK
TME_CURRENCY=EUR
TME_LANGUAGE=SK
```

> [!NOTE]
> If the API returns `E_AUTHORIZATION_FAILED (Access Denied)`, ensure that the registered Application on [developers.tme.eu](https://developers.tme.eu) has API Action permissions (such as `Products/Search` and `Products/GetPricesAndStocks`) enabled.
