"""OSINT (Open Source Intelligence) tools — Phase 1: Zero-credential capabilities.

These tools provide on-demand information gathering without requiring credentials,
respecting D-62's 4-token budget. All tools are:
- Read-only (D-13 compliant)
- Query-triggered only (D-34 compliant)
- Typed schemas (D-04 compliant)
- No ambient feeds (D-34 compliant)

Phase 1 implements:
1. Currency conversion (OpenExchangeRates free tier)
2. WHOIS lookup (command-line or API)
3. IP geolocation (IPAPI free)
4. SSL certificate info (crt.sh)
5. arXiv paper search (arXiv API)
"""

from __future__ import annotations

import re
import socket
import subprocess
import urllib.parse
from datetime import datetime

import httpx

from mushegh.brain.tools.base import _client, tool_error


# =============================================================================
# 1. CURRENCY CONVERSION
# =============================================================================

async def convert_currency(args: dict) -> str:
    """Convert an amount from one currency to another using live exchange rates.
    
    Uses OpenExchangeRates free tier (no API key required for limited use).
    Falls back to European Central Bank rates if primary fails.
    """
    amount = args.get("amount")
    from_currency = (args.get("from") or "").upper()
    to_currency = (args.get("to") or "").upper()
    
    if not amount or not from_currency or not to_currency:
        return ("I need the amount, the source currency and the target currency, sir. "
                "For example: 'convert 100 USD to EUR'.")
    
    try:
        amount_float = float(amount)
    except ValueError:
        return f"'{amount}' isn't a valid number, sir."
    
    if from_currency == to_currency:
        return f"{amount} {from_currency} is {amount} {to_currency}, sir."
    
    try:
        # Try OpenExchangeRates free tier (no auth required)
        # The POOLED client (01.J18): this module was the last in the belt still building its own
        # httpx.AsyncClient, five times, and every call paid a full TLS handshake that the next
        # call repeated. `test_api_policy.py` is what noticed. Not `async with` — the client is
        # shared, and closing it here would drop the pool on every call, which is the cost the
        # pool exists to remove.
        client = _client(f"https://open.er-api.com/v6/latest/{from_currency}", timeout=10.0)
        # OpenExchangeRates latest endpoint (no key needed for limited use)
        url = f"https://open.er-api.com/v6/latest/{from_currency}"
        response = await client.get(url)

        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success":
                rates = data.get("rates", {})
                if to_currency in rates:
                    rate = rates[to_currency]
                    converted = amount_float * rate
                    as_of = data.get("time_last_update_unix", 0)
                    timestamp = datetime.fromtimestamp(as_of).strftime("%Y-%m-%d %H:%M UTC")
                    return (f"{amount} {from_currency} = {converted:.4f} {to_currency} "
                            f"(rate: {rate:.6f}, as of {timestamp}).")

        # Fallback: European Central Bank (ECB) - no auth required
        if from_currency == "EUR" or to_currency == "EUR":
            ecb_url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.json"
            response = await client.get(ecb_url)
            if response.status_code == 200:
                ecb_data = response.json()
                # ECB provides EUR base rates
                if from_currency == "EUR":
                    if to_currency in ecb_data.get("rates", {}):
                        rate = ecb_data["rates"][to_currency]
                        converted = amount_float * rate
                        return f"{amount} EUR = {converted:.4f} {to_currency} (ECB rate)."
                    return f"I don't have the {to_currency} rate from ECB, sir."
                else:
                    # Convert FROM to EUR first, then to target
                    if from_currency in ecb_data.get("rates", {}):
                        from_to_eur = 1.0 / ecb_data["rates"][from_currency]
                    else:
                        return f"I don't have the {from_currency} rate from ECB, sir."

                    if to_currency in ecb_data.get("rates", {}):
                        eur_to_target = ecb_data["rates"][to_currency]
                        rate = from_to_eur * eur_to_target
                        converted = amount_float * rate
                        return f"{amount} {from_currency} = {converted:.4f} {to_currency} (via ECB)."

        # Final fallback: Use fxratesapi.net (no auth)
        fx_url = f"https://api.fxratesapi.net/latest?base={from_currency}"
        response = await client.get(fx_url)
        if response.status_code == 200:
            fx_data = response.json()
            if fx_data.get("success") and to_currency in fx_data.get("rates", {}):
                rate = fx_data["rates"][to_currency]
                converted = amount_float * rate
                return f"{amount} {from_currency} = {converted:.4f} {to_currency} (fxratesapi)."

        return f"I couldn't fetch the exchange rate for {from_currency} to {to_currency}, sir."
            
    except httpx.TimeoutException:
        return tool_error("currency conversion", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("currency conversion", e)
    except Exception as e:
        return tool_error("currency conversion", e)


# =============================================================================
# 2. WHOIS LOOKUP
# =============================================================================

async def whois_lookup(args: dict) -> str:
    """Look up domain registration information.
    
    Uses command-line whois or web-based lookup as fallback.
    """
    domain = (args.get("domain") or "").strip().lower()
    
    if not domain:
        return "What domain should I look up, sir?"
    
    # Validate domain format
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9](\.[a-z0-9][a-z0-9\-]{1,61}[a-z0-9])*$", domain, re.I):
        return f"'{domain}' doesn't look like a valid domain name, sir."
    
    try:
        # Try command-line whois first (fastest, no network)
        try:
            result = subprocess.run(
                ["whois", domain],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                # Parse key information
                output = result.stdout
                registrant = _extract_whois_field(output, ["Registrant", "Owner", "Owner Name", "Owner: "])
                registrar = _extract_whois_field(output, ["Registrar", "Registration Service", "Sponsoring Registrar"])
                creation = _extract_whois_field(output, ["Creation Date", "Registered on", "created", "Registered "])
                expiration = _extract_whois_field(output, ["Expiration Date", "Registry Expiry", "expir", "Expires on"])
                name_servers = _extract_whois_field(output, ["Name Server", "nameserver", "nserver"], multi=True)
                
                response_lines = [f"WHOIS for **{domain}**:"]
                if registrant:
                    response_lines.append(f"• Registrant: {registrant}")
                if registrar:
                    response_lines.append(f"• Registrar: {registrar}")
                if creation:
                    response_lines.append(f"• Created: {creation}")
                if expiration:
                    response_lines.append(f"• Expires: {expiration}")
                if name_servers:
                    response_lines.append(f"• Name Servers: {', '.join(name_servers[:5])}")
                
                return "\n".join(response_lines)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Fallback: Use RDAP (Registration Data Access Protocol) - modern replacement for WHOIS
        # Pooled client — see the note in the currency block above.
        rdap_url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
        client = _client(rdap_url, timeout=10.0)
        
        try:
            response = await client.get(rdap_url)
            if response.status_code == 200:
                data = response.json()
                response_lines = [f"WHOIS for **{domain}**:"]
                
                # Extract registrar
                events = data.get("events", [])
                for event in events:
                    if event.get("eventAction") == "registration":
                        response_lines.append(f"• Created: {event.get('eventDate', 'Unknown')}")
                    elif event.get("eventAction") == "expiration":
                        response_lines.append(f"• Expires: {event.get('eventDate', 'Unknown')}")
                
                # Extract registrar name from entities
                entities = data.get("entities", [])
                registrar_name = None
                for entity in entities:
                    if entity.get("roles") and "registrar" in entity.get("roles", []):
                        # Get the fn (formatted name) from vcardArray
                        vcard = entity.get("vcardArray", [])
                        for item in vcard:
                            if isinstance(item, list) and len(item) >= 4:
                                if item[1] == "fn" or item[1] == "org" or item[1] == "organization":
                                    registrar_name = item[3] if len(item) > 3 else None
                                    if registrar_name:
                                        break
                        if registrar_name:
                            break
                
                if registrar_name:
                    response_lines.append(f"• Registrar: {registrar_name}")
                else:
                    # Fallback: try links
                    for link in data.get("links", []):
                        if link.get("rel") == "registrar":
                            registrar = link.get("value", "")
                            if registrar:
                                registrar_domain = urllib.parse.urlparse(registrar).netloc
                                if registrar_domain:
                                    response_lines.append(f"• Registrar: {registrar_domain}")
                                    break
                
                # Extract name servers - RDAP returns them as dicts with ldhName field
                name_servers = data.get("nameservers", [])
                if name_servers:
                    # RDAP returns name servers as a list of dicts with ldhName field
                    ns_list = []
                    for ns in name_servers[:5]:
                        if isinstance(ns, str):
                            ns_list.append(ns)
                        elif isinstance(ns, dict):
                            # Try to get ldhName, hostname, or value
                            for key in ["ldhName", "hostname", "value"]:
                                if key in ns and isinstance(ns[key], str):
                                    ns_list.append(ns[key])
                                    break
                    if ns_list:
                        response_lines.append(f"• Name Servers: {', '.join(ns_list)}")
                
                if len(response_lines) > 1:
                    return "\n".join(response_lines)
        except (httpx.RequestError, ValueError, KeyError):
            pass

        # Final fallback: Use ICANN lookup (no auth)
        icann_url = f"https://lookup.icann.org/v2/{domain}"
        try:
            response = await client.get(icann_url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "registration" in data:
                        reg = data["registration"]
                        response_lines = [f"WHOIS for **{domain}**:"]
                        if reg.get("registrant"):
                            response_lines.append(f"• Registrant: {reg['registrant']}")
                        if reg.get("registrar"):
                            response_lines.append(f"• Registrar: {reg['registrar']}")
                        if reg.get("createdDate"):
                            response_lines.append(f"• Created: {reg['createdDate']}")
                        if reg.get("expirationDate"):
                            response_lines.append(f"• Expires: {reg['expirationDate']}")
                        return "\n".join(response_lines)
                except ValueError:
                    # Not JSON, might be HTML
                    pass
        except httpx.RequestError:
            pass
            
        return f"I couldn't look up the WHOIS information for {domain}, sir."
            
    except httpx.TimeoutException:
        return tool_error("WHOIS lookup", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("WHOIS lookup", e)
    except Exception as e:
        return tool_error("WHOIS lookup", e)


def _extract_whois_field(text: str, keys: list, multi: bool = False) -> list[str] | str | None:
    """Extract a field from WHOIS text."""
    results = []
    for key in keys:
        pattern = re.compile(fr"{key}\s*[:=]\s*(.+?)(?=\n\S+:\s|\n\n|$)", re.IGNORECASE | re.MULTILINE)
        matches = pattern.findall(text)
        if matches:
            for match in matches:
                clean = match.strip()
                if clean and clean not in results:
                    results.append(clean)
    if not results:
        return None
    if multi:
        return results
    return results[0]


# =============================================================================
# 3. IP GEOLOCATION
# =============================================================================

async def ip_geolocate(args: dict) -> str:
    """Geolocate an IP address to find its country, city, ISP, and coordinates.
    
    Uses IPAPI (free tier: 45 requests/minute, no API key required).
    """
    ip = (args.get("ip") or "").strip()
    
    if not ip:
        # If no IP provided, use the public IP of the brain host
        ip = "auto"
    
    try:
        # Pooled client — see the note in the currency block above.
        client = _client("https://api.ipify.org?format=json", timeout=10.0)
        if ip == "auto":
            # Get our public IP first
            ip_response = await client.get("https://api.ipify.org?format=json")
            if ip_response.status_code == 200:
                ip = ip_response.json().get("ip", "")
            else:
                return "I couldn't determine your public IP, sir."

        # Validate IP format
        try:
            socket.inet_aton(ip) if "." in ip else socket.inet_pton(socket.AF_INET6, ip)
        except (socket.error, OSError):
            return f"'{ip}' isn't a valid IP address, sir."

        # Use IPAPI (no auth required)
        url = f"http://ip-api.com/json/{ip}"
        response = await client.get(url)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")

            if status == "success":
                country = data.get("country", "Unknown")
                country_code = data.get("countryCode", "")
                region = data.get("regionName", "")
                city = data.get("city", "")
                zip_code = data.get("zip", "")
                isp = data.get("isp", "")
                org = data.get("org", "")
                lat = data.get("lat")
                lon = data.get("lon")
                timezone = data.get("timezone", "")

                response_lines = [f"IP **{ip}**:"]
                if country:
                    response_lines.append(f"• Country: {country} ({country_code})")
                if region:
                    response_lines.append(f"• Region: {region}")
                if city:
                    response_lines.append(f"• City: {city}")
                if zip_code:
                    response_lines.append(f"• ZIP: {zip_code}")
                if lat and lon:
                    response_lines.append(f"• Coordinates: {lat}, {lon}")
                if timezone:
                    response_lines.append(f"• Timezone: {timezone}")
                if isp or org:
                    response_lines.append(f"• Provider: {isp or org}")

                return "\n".join(response_lines)
            elif status == "fail":
                return f"IP lookup failed: {data.get('message', 'unknown error')}, sir."
            
            return f"I couldn't geolocate IP {ip}, sir."
            
    except httpx.TimeoutException:
        return tool_error("IP geolocation", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("IP geolocation", e)
    except Exception as e:
        return tool_error("IP geolocation", e)


# =============================================================================
# 4. SSL CERTIFICATE INFO
# =============================================================================

async def ssl_cert_info(args: dict) -> str:
    """Get SSL certificate information for a domain.
    
    Uses crt.sh (Certificate Transparency logs) - free, no auth required.
    """
    domain = (args.get("domain") or "").strip().lower()
    
    if not domain:
        return "What domain's SSL certificate should I check, sir?"
    
    # Validate domain
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9](\.[a-z0-9][a-z0-9\-]{1,61}[a-z0-9])*$", domain, re.I):
        return f"'{domain}' doesn't look like a valid domain name, sir."
    
    try:
        # Pooled client — see the note in the currency block above.
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        client = _client(url, timeout=15.0)
        # Use crt.sh (no auth required)
        response = await client.get(url)

        if response.status_code == 200:
            certs = response.json()

            if not certs:
                return f"No SSL certificates found for {domain}, sir."

            # Get the most recent certificate
            most_recent = certs[0]

            common_name = most_recent.get("common_name", "")
            issuer = most_recent.get("issuer_name", "")
            valid_from = most_recent.get("not_before", "")
            valid_to = most_recent.get("not_after", "")

            response_lines = [f"SSL Certificates for **{domain}**:"]
            response_lines.append(f"• Most recent: {common_name or domain}")
            if issuer:
                response_lines.append(f"• Issuer: {issuer}")
            if valid_from:
                response_lines.append(f"• Valid from: {valid_from}")
            if valid_to:
                response_lines.append(f"• Valid until: {valid_to}")
            response_lines.append(f"• Total certificates: {len(certs)}")

            return "\n".join(response_lines)

        return f"I couldn't fetch SSL information for {domain}, sir."
            
    except httpx.TimeoutException:
        return tool_error("SSL cert lookup", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("SSL cert lookup", e)
    except Exception as e:
        return tool_error("SSL cert lookup", e)


# =============================================================================
# 5. ARXIV PAPER SEARCH
# =============================================================================

async def search_arxiv(args: dict) -> str:
    """Search for academic papers on arXiv.org.
    
    Uses arXiv API (free, no auth required).
    """
    query = (args.get("query") or "").strip()
    max_results = args.get("max_results", 5)
    
    if not query:
        return "What should I search for on arXiv, sir?"
    
    try:
        max_results = int(max_results)
        if max_results < 1 or max_results > 10:
            max_results = 5
    except (ValueError, TypeError):
        max_results = 5
    
    try:
        # arXiv API endpoint. Pooled client — see the note in the currency block above.
        url = (f"http://export.arxiv.org/api/query?search_query={query}&start=0"
               f"&max_results={max_results}&sortBy=relevance&sortOrder=descending")
        client = _client(url, timeout=10.0)
        response = await client.get(url)

        if response.status_code == 200:
            # Parse Atom XML response
            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.text)

            # Define namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            entries = root.findall("atom:entry", ns)

            if not entries:
                return f"No papers found for '{query}', sir."

            response_lines = [f"arXiv results for **'{query}'**:"]

            for i, entry in enumerate(entries[:max_results], 1):
                title = entry.find("atom:title", ns)
                title_text = title.text if title is not None else "Untitled"

                arxiv_id = entry.find("atom:id", ns)
                arxiv_id_text = arxiv_id.text if arxiv_id is not None else ""

                authors = entry.findall("atom:author/atom:name", ns)
                author_names = ", ".join([a.text for a in authors if a.text]) if authors else "Unknown"

                published = entry.find("atom:published", ns)
                published_text = published.text if published is not None else ""

                summary = entry.find("atom:summary", ns)
                summary_text = ((summary.text[:200] + "...")
                                if summary is not None and summary.text else "No abstract")

                response_lines.append(f"\n{i}. **{title_text}**")
                response_lines.append(f"   ID: {arxiv_id_text}")
                response_lines.append(f"   Authors: {author_names}")
                response_lines.append(f"   Published: {published_text}")
                response_lines.append(f"   Abstract: {summary_text}")

            return "\n".join(response_lines)

        return f"I couldn't search arXiv for '{query}', sir."
            
    except httpx.TimeoutException:
        return tool_error("arXiv search", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("arXiv search", e)
    except Exception as e:
        return tool_error("arXiv search", e)


# =============================================================================
# SCHEMAS AND HANDLERS
# =============================================================================

SCHEMAS = [
    # 1. Currency Conversion
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount from one currency to another using live exchange rates. "
                           "Use when the owner asks 'how much is X in Y' or 'convert X to Y'. "
                           "Supports 160+ currencies. Free tier, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount to convert (e.g., 100, 100.50)"
                    },
                    "from": {
                        "type": "string",
                        "description": "Source currency code (e.g., USD, EUR, GBP)"
                    },
                    "to": {
                        "type": "string",
                        "description": "Target currency code (e.g., EUR, USD, JPY)"
                    }
                },
                "required": ["amount", "from", "to"]
            }
        }
    },
    # 2. WHOIS Lookup
    {
        "type": "function",
        "function": {
            "name": "whois_lookup",
            "description": "Look up domain registration information (WHOIS). "
                           "Use when the owner asks 'who owns this domain' or 'when was this domain registered'. "
                           "Returns registrant, registrar, creation/expiration dates, and name servers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to look up (e.g., google.com, example.org)"
                    }
                },
                "required": ["domain"]
            }
        }
    },
    # 3. IP Geolocation
    {
        "type": "function",
        "function": {
            "name": "ip_geolocate",
            "description": "Geolocate an IP address to find its country, city, ISP, and coordinates. "
                           "Use when the owner asks 'where is this IP' or 'who owns this IP'. "
                           "If no IP provided, uses the brain's public IP. Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "IP address to geolocate (e.g., 8.8.8.8). "
                                       "Use 'auto' to use the brain's public IP."
                    }
                },
                "required": []  # ip is optional (defaults to auto)
            }
        }
    },
    # 4. SSL Certificate Info
    {
        "type": "function",
        "function": {
            "name": "ssl_cert_info",
            "description": "Get SSL certificate information for a domain from Certificate Transparency logs. "
                           "Use when the owner asks 'who issued this SSL certificate' or 'when does this cert expire'. "
                           "Shows issuer, validity period, and certificate history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to check (e.g., google.com, example.org)"
                    }
                },
                "required": ["domain"]
            }
        }
    },
    # 5. arXiv Paper Search
    {
        "type": "function",
        "function": {
            "name": "search_arxiv",
            "description": "Search for academic papers on arXiv.org. "
                           "Use when the owner asks 'find papers about X' or 'what's new in Y research'. "
                           "Returns title, authors, publication date, and abstract. Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'machine learning', 'quantum computing')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-10, default 5)",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["query"]
            }
        }
    }
]

HANDLERS = {
    "convert_currency": convert_currency,
    "whois_lookup": whois_lookup,
    "ip_geolocate": ip_geolocate,
    "ssl_cert_info": ssl_cert_info,
    "search_arxiv": search_arxiv,
}
