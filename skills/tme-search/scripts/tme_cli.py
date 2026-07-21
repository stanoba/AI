import os
import sys
import json
import time
import base64
import argparse
import requests
from pathlib import Path

# Path definitions
SKILL_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = SKILL_DIR.parent.parent
TOKEN_CACHE_FILE = SKILL_DIR / ".token_cache.json"
FAVORITES_FILE = WORKSPACE_ROOT / "tme_favorites.json"

def load_env():
    env_paths = [SKILL_DIR / ".env", WORKSPACE_ROOT / ".env"]
    for path in env_paths:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_env()

TME_TOKEN = os.environ.get("TME_TOKEN", "")
TME_SECRET = os.environ.get("TME_SECRET", "")
TME_COUNTRY = os.environ.get("TME_COUNTRY", "SK")
TME_CURRENCY = os.environ.get("TME_CURRENCY", "EUR")
TME_LANGUAGE = os.environ.get("TME_LANGUAGE", "SK")

def get_access_token() -> str:
    """Obtains OAuth 2.0 access token using client credentials, with local caching."""
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if cache.get("expires_at", 0) > time.time() + 30:
                    return cache["access_token"]
        except Exception:
            pass

    auth_str = f"{TME_TOKEN}:{TME_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_auth}"
    }
    data = {"grant_type": "client_credentials"}
    
    url = "https://api.tme.eu/auth/token"
    res = requests.post(url, headers=headers, data=data, timeout=10)
    
    if res.status_code != 200:
        raise RuntimeError(f"TME OAuth Failed (HTTP {res.status_code}): {res.text}")
        
    token_data = res.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 300)
    
    try:
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "access_token": access_token,
                "expires_at": time.time() + expires_in
            }, f)
    except Exception:
        pass
        
    return access_token

def call_api(endpoint: str, params: dict = None, method: str = "GET") -> dict:
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": TME_LANGUAGE.lower()
    }
    url = f"https://api.tme.eu/{endpoint.lstrip('/')}"
    
    if method.upper() == "GET":
        res = requests.get(url, headers=headers, params=params, timeout=10)
    else:
        res = requests.post(url, headers=headers, data=params, timeout=10)
        
    if res.status_code != 200:
        return {"status": "ERROR", "error": f"HTTP {res.status_code}: {res.text}"}
    return res.json()

def search_products(query: str, in_stock_only: bool = False, limit: int = 10, output_json: bool = False):
    res_sym = call_api("products/symbols", params={"paginate[limit]": 500})
    if res_sym.get("status") != "OK":
        err_msg = f"Error fetching symbols: {res_sym.get('error')}"
        if output_json:
            print(json.dumps({"status": "ERROR", "error": err_msg}))
        else:
            print(err_msg)
        return
        
    all_symbols = res_sym.get("data", {}).get("elements", [])
    query_upper = query.upper()
    matching_symbols = [s for s in all_symbols if query_upper in s.upper()]
    
    if not matching_symbols:
        matching_symbols = all_symbols[:30]
        
    target_symbols = matching_symbols[:50]
    
    data_res = call_api("products/data", params={
        "symbols[]": target_symbols,
        "scope[]": ["prices", "stock"],
        "country": TME_COUNTRY,
        "currency": TME_CURRENCY
    })
    
    if data_res.get("status") != "OK":
        err_msg = f"Error fetching product data: {data_res.get('error')}"
        if output_json:
            print(json.dumps({"status": "ERROR", "error": err_msg}))
        else:
            print(err_msg)
        return
        
    elements = data_res.get("data", {}).get("elements", [])
    
    results = []
    for elem in elements:
        stock = elem.get("stock_quantity", 0) or 0
        if in_stock_only and stock <= 0:
            continue
            
        sym = elem.get("symbol")
        unit_info = elem.get("unit", {}).get("short_name", "pcs")
        prices = elem.get("prices", {}).get("elements", []) if elem.get("prices") else []
        
        p1 = prices[0].get("price", None) if prices else None
        p100 = None
        for pr in prices:
            if pr.get("amount", 0) >= 100:
                p100 = pr.get("price")
                break
                
        results.append({
            "symbol": sym,
            "stock": stock,
            "unit": unit_info,
            "price_1": p1,
            "price_100": p100,
            "currency": TME_CURRENCY,
            "all_prices": prices
        })
        if len(results) >= limit:
            break

    if output_json:
        print(json.dumps({"status": "OK", "query": query, "count": len(results), "results": results}, indent=2, ensure_ascii=False))
    else:
        print(f"\n### TME Product Search Results for '{query}' (In-Stock Only: {in_stock_only})\n")
        print("| Symbol | Stock | Unit | Price (1x) | Price (100x) |")
        print("| :--- | :---: | :---: | :---: | :---: |")
        for r in results:
            p1_str = f"{r['price_1']} {TME_CURRENCY}" if r['price_1'] is not None else "N/A"
            p100_str = f"{r['price_100']} {TME_CURRENCY}" if r['price_100'] is not None else "N/A"
            print(f"| `{r['symbol']}` | **{r['stock']:,}** | {r['unit']} | {p1_str} | {p100_str} |")
        print("\n")

def get_product_details(symbols: list, output_json: bool = False):
    data_res = call_api("products/data", params={
        "symbols[]": symbols,
        "scope[]": ["prices", "stock"],
        "country": TME_COUNTRY,
        "currency": TME_CURRENCY
    })
    files_res = call_api("products/files", params={"symbols[]": symbols})
    
    data_map = {}
    if data_res.get("status") == "OK":
        for elem in data_res.get("data", {}).get("elements", []):
            data_map[elem["symbol"]] = elem
            
    files_map = {}
    if files_res.get("status") == "OK":
        for elem in files_res.get("data", {}).get("elements", []):
            files_map[elem["symbol"]] = elem

    results = []
    for sym in symbols:
        data_info = data_map.get(sym, {})
        file_info = files_map.get(sym, {})
        
        stock = data_info.get("stock_quantity", 0) or 0
        prices = data_info.get("prices", {}).get("elements", []) if data_info.get("prices") else []
        docs = file_info.get("documents", {}).get("elements", []) if file_info.get("documents") else []
        
        datasheet_url = None
        for d in docs:
            if d.get("type") == "DTE":
                url = d.get("url", "")
                datasheet_url = f"https:{url}" if url.startswith("//") else url
                break
                
        img_info = file_info.get("assets", {}).get("primary_photo", {})
        photo_url = img_info.get("prime") if img_info else None
        if photo_url and photo_url.startswith("//"):
            photo_url = f"https:{photo_url}"
            
        results.append({
            "symbol": sym,
            "stock": stock,
            "prices": prices,
            "currency": TME_CURRENCY,
            "datasheet_url": datasheet_url,
            "photo_url": photo_url
        })
        
    if output_json:
        print(json.dumps({"status": "OK", "details": results}, indent=2, ensure_ascii=False))
    else:
        print("\n### Product Details & Datasheets\n")
        for item in results:
            sym = item["symbol"]
            print(f"#### `{sym}`")
            print(f"- **Stock Availability**: **{item['stock']:,}** pcs")
            if item["prices"]:
                print("- **Price Tiers**:")
                for pr in item["prices"][:4]:
                    print(f"  - Qty {pr.get('amount')}+: **{pr.get('price')} {TME_CURRENCY}**")
            if item["datasheet_url"]:
                print(f"- [PDF] **Datasheet**: [{sym} Datasheet]({item['datasheet_url']})")
            if item["photo_url"]:
                print(f"- [IMAGE] **Product Photo**: [View Image]({item['photo_url']})")
            print()

def load_favorites():
    if FAVORITES_FILE.exists():
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_favorites(favs):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, indent=2)

def favorite_add(symbol: str, role: str = ""):
    favs = load_favorites()
    for item in favs:
        if item["symbol"].upper() == symbol.upper():
            item["role"] = role or item.get("role", "")
            save_favorites(favs)
            print(f"Updated favorite '{symbol}' in {FAVORITES_FILE}")
            return
    favs.append({"symbol": symbol.upper(), "role": role})
    save_favorites(favs)
    print(f"Added '{symbol}' to favorites list ({FAVORITES_FILE})")

def favorite_list(output_json: bool = False):
    favs = load_favorites()
    if not favs:
        if output_json:
            print(json.dumps({"status": "OK", "favorites": []}))
        else:
            print("No favorites saved yet in project.")
        return
        
    symbols = [f["symbol"] for f in favs]
    
    data_res = call_api("products/data", params={
        "symbols[]": symbols,
        "scope[]": ["prices", "stock"],
        "country": TME_COUNTRY,
        "currency": TME_CURRENCY
    })
    
    data_map = {}
    if data_res.get("status") == "OK":
        for elem in data_res.get("data", {}).get("elements", []):
            data_map[elem["symbol"]] = elem

    results = []
    for item in favs:
        sym = item["symbol"]
        role = item.get("role", "-")
        data_info = data_map.get(sym, {})
        stock = data_info.get("stock_quantity", 0) or 0
        prices = data_info.get("prices", {}).get("elements", []) if data_info.get("prices") else []
        unit_price = prices[0].get("price", None) if prices else None
        
        results.append({
            "symbol": sym,
            "role": role,
            "stock": stock,
            "unit_price": unit_price,
            "currency": TME_CURRENCY,
            "in_stock": stock > 0
        })

    if output_json:
        print(json.dumps({"status": "OK", "favorites": results}, indent=2, ensure_ascii=False))
    else:
        print("\n### Project Favorites / BOM Parts List\n")
        print("| Symbol | Designated Role | Stock | Unit Price | Status |")
        print("| :--- | :--- | :---: | :---: | :---: |")
        for r in results:
            status_str = "[IN STOCK]" if r["in_stock"] else "[OUT OF STOCK]"
            price_str = f"{r['unit_price']} {TME_CURRENCY}" if r['unit_price'] is not None else "N/A"
            print(f"| `{r['symbol']}` | {r['role']} | **{r['stock']:,}** | {price_str} | {status_str} |")
        print("\n")

def fetch_shared_favorite_list(url_or_hash: str, output_json: bool = False):
    import re
    hash_match = re.search(r"([a-fA-F0-9]{40})", url_or_hash)
    if not hash_match:
        print("Invalid TME shared favorite URL or hash.")
        return
    token = hash_match.group(1)
    
    endpoint_url = f"https://www.tme.eu/ajax/common/new-favourites/{token}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(endpoint_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"Error fetching shared list (HTTP {res.status_code})")
            return
        data = res.json()
    except Exception as e:
        print(f"Failed to retrieve shared list: {e}")
        return

    name = data.get("name", "Shared Favorites List")
    elements = data.get("elements", [])
    
    results = []
    for elem in elements:
        sym = elem.get("symbol")
        mfr = elem.get("manufacturer", {}).get("name", "")
        desc = elem.get("description", "")
        results.append({
            "symbol": sym,
            "manufacturer": mfr,
            "description": desc
        })
        
    if output_json:
        print(json.dumps({"status": "OK", "name": name, "token": token, "items": results}, indent=2, ensure_ascii=False))
    else:
        print(f"\n### TME Shared Favorites List: '{name}'\n")
        print("| Symbol | Manufacturer | Description |")
        print("| :--- | :--- | :--- |")
        for r in results:
            print(f"| `{r['symbol']}` | {r['manufacturer']} | {r['description']} |")
        print("\n")

def main():
    parser = argparse.ArgumentParser(description="TME.eu Component Search & Stock Checker CLI")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data instead of formatted Markdown")
    subparsers = parser.add_subparsers(dest="command")
    
    # Search
    search_parser = subparsers.add_parser("search", help="Search components")
    search_parser.add_argument("query", type=str, help="Search query (e.g. '1N4007')")
    search_parser.add_argument("--in-stock", action="store_true", help="Filter in-stock items only")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    search_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # Details
    details_parser = subparsers.add_parser("details", help="Get component details and datasheets")
    details_parser.add_argument("symbols", nargs="+", help="TME product symbols (e.g. 1N4007-DIO)")
    details_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # Favorite
    fav_parser = subparsers.add_parser("favorite", help="Manage favorites list")
    fav_sub = fav_parser.add_subparsers(dest="fav_action")
    fav_add = fav_sub.add_parser("add")
    fav_add.add_argument("symbol", type=str)
    fav_add.add_argument("--role", type=str, default="", help="Designated role (e.g. 'Q1 PWM MOSFET')")
    
    fav_list = fav_sub.add_parser("list")
    fav_list.add_argument("--json", action="store_true", help="Output raw JSON")
    
    fav_import = fav_sub.add_parser("import", help="Fetch items from a public shared TME favorites URL or hash token")
    fav_import.add_argument("url_or_hash", type=str, help="Shared TME favorite list URL or token hash")
    fav_import.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    output_json = getattr(args, "json", False)
    
    if args.command == "search":
        search_products(args.query, in_stock_only=args.in_stock, limit=args.limit, output_json=output_json)
    elif args.command == "details":
        get_product_details(args.symbols, output_json=output_json)
    elif args.command == "favorite":
        if args.fav_action == "add":
            favorite_add(args.symbol, args.role)
        elif args.fav_action == "import":
            fetch_shared_favorite_list(args.url_or_hash, output_json=output_json)
        else:
            favorite_list(output_json=output_json)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
