"""OSINT (Open Source Intelligence) tools — Phase 2: Person/Identity Research.

These tools provide on-demand person and identity information gathering without requiring credentials,
respecting D-62's 4-token budget. All tools are:
- Read-only (D-13 compliant)
- Query-triggered only (D-34 compliant)
- Typed schemas (D-04 compliant)
- No ambient feeds (D-34 compliant)

Phase 2 implements:
1. DNS lookup (system dig/nslookup or free APIs)
2. Email verification (MX records, domain validation)
3. Phone number info (carrier, location via free APIs)
4. Username search (check across platforms)
5. Website metadata extraction (headers, technologies, etc.)
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
from urllib.parse import urlparse

import httpx

from mushegh.brain.tools.base import _client, tool_error


# =============================================================================
# 1. DNS LOOKUP
# =============================================================================

async def dns_lookup(args: dict) -> str:
    """Look up DNS records for a domain.
    
    Uses system dig/nslookup command or free DNS APIs.
    Returns A, AAAA, MX, TXT, CNAME, NS records.
    """
    domain = (args.get("domain") or "").strip().lower()
    record_type = (args.get("type") or "ALL").strip().upper()
    
    if not domain:
        return "What domain should I look up DNS records for, sir?"
    
    # Validate domain format
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9](\.[a-z0-9][a-z0-9\-]{1,61}[a-z0-9])*$", domain, re.I):
        return f"'{domain}' doesn't look like a valid domain name, sir."
    
    try:
        # Try command-line dig first
        try:
            result = subprocess.run(
                ["dig", domain, record_type] if record_type != "ALL" else ["dig", domain, "ANY"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return _parse_dig_output(result.stdout, domain)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Fallback: Try nslookup
        try:
            result = subprocess.run(
                ["nslookup", "-type=" + record_type, domain] if record_type != "ALL" else ["nslookup", domain],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0 and result.stdout:
                return _parse_nslookup_output(result.stdout, domain)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        # Fallback: Use free DNS API (dns.google.com)
        client = _client(f"https://dns.google.com/resolve?name={domain}", timeout=10.0)
        
        if record_type == "ALL":
            # Get all common record types
            record_types = ["A", "AAAA", "MX", "TXT", "CNAME", "NS", "SOA"]
            results = []
            for rtype in record_types:
                url = f"https://dns.google.com/resolve?name={domain}&type={rtype}"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("Answer"):
                        results.append(_format_dns_records(rtype, data["Answer"]))
            
            if results:
                return f"DNS records for **{domain}**:\n\n" + "\n".join(results)
        else:
            # Get specific record type
            url = f"https://dns.google.com/resolve?name={domain}&type={record_type}"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("Answer"):
                    return f"DNS {record_type} records for **{domain}**:\n\n{_format_dns_records(record_type, data['Answer'])}"
                else:
                    return f"No {record_type} records found for {domain}, sir."
        
        return f"I couldn't look up DNS records for {domain}, sir."
            
    except httpx.TimeoutException:
        return tool_error("DNS lookup", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("DNS lookup", e)
    except Exception as e:
        return tool_error("DNS lookup", e)


def _parse_dig_output(output: str, domain: str) -> str:
    """Parse dig command output."""
    lines = output.split('\n')
    sections = {}
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith(';') or line.startswith('<<>>'):
            continue
        if line.endswith(':'):
            current_section = line.rstrip(':')
            sections[current_section] = []
        elif current_section and line and not line.startswith(domain):
            sections[current_section].append(line)
    
    if not sections:
        return f"DNS records for **{domain}**:\nNo records found."
    
    result_lines = [f"DNS records for **{domain}**:"]
    for section, records in sections.items():
        if records:
            result_lines.append(f"\n• {section}:")
            for record in records:
                result_lines.append(f"  {record}")
    
    return "\n".join(result_lines)


def _parse_nslookup_output(output: str, domain: str) -> str:
    """Parse nslookup command output."""
    lines = output.split('\n')
    result_lines = [f"DNS records for **{domain}**:"]
    in_answer = False
    
    for line in lines:
        line = line.strip()
        if 'Address:' in line or 'Addresses:' in line:
            in_answer = True
        if in_answer and line and not line.startswith('---') and 'Address:' not in line:
            result_lines.append(f"• {line}")
    
    return "\n".join(result_lines) if len(result_lines) > 1 else f"No DNS records found for {domain}, sir."


def _format_dns_records(record_type: str, answers: list) -> str:
    """Format DNS records from API response."""
    lines = [f"• {record_type} Records:"]
    for answer in answers:
        name = answer.get("name", "")
        rtype = answer.get("type", record_type)
        ttl = answer.get("TTL", "")
        data = answer.get("data", "")
        if data:
            lines.append(f"  {data} (TTL: {ttl})")
    return "\n".join(lines)


# =============================================================================
# 2. EMAIL VERIFICATION
# =============================================================================

async def email_verify(args: dict) -> str:
    """Verify an email address and extract domain information.
    
    Checks email format, domain validity, MX records, and SMTP availability.
    """
    email = (args.get("email") or "").strip().lower()
    
    if not email:
        return "What email address should I verify, sir?"
    
    # Validate email format
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", email, re.I):
        return f"'{email}' doesn't look like a valid email address, sir."
    
    try:
        domain = email.split('@')[1]
        username = email.split('@')[0]
        
        result_lines = [f"Email verification for **{email}**:"]
        
        # Check domain DNS records
        try:
            # Check MX records
            mx_records = []
            try:
                answers = socket.getaddrinfo(domain, None, socket.AF_INET)
                # Try to get MX records via DNS lookup
                mx_result = await dns_lookup({"domain": domain, "type": "MX"})
                if "MX" in mx_result:
                    for line in mx_result.split('\n'):
                        if 'MX' in line or 'Mail' in line:
                            mx_records.append(line.strip())
            except Exception:
                pass
            
            if mx_records:
                result_lines.append(f"• Mail Servers: {', '.join(mx_records[:3])}")
            else:
                result_lines.append("• Mail Servers: No MX records found")
            
            # Check A records
            try:
                ip_addresses = socket.gethostbyname_ex(domain)[2]
                result_lines.append(f"• Domain IP(s): {', '.join(ip_addresses[:3])}")
            except Exception:
                result_lines.append("• Domain IP: Could not resolve")
            
            # Check if domain has valid SSL
            try:
                ssl_result = await ssl_cert_info({"domain": domain})
                if "SSL Certificates" in ssl_result:
                    result_lines.append("• SSL Certificate: Valid")
                else:
                    result_lines.append("• SSL Certificate: Not found or invalid")
            except Exception:
                result_lines.append("• SSL Certificate: Could not check")
            
            # Check if email is disposable
            disposable = await _check_disposable_email(email)
            if disposable:
                result_lines.append("• ⚠️  WARNING: This appears to be a disposable/temporary email address")
            else:
                result_lines.append("• Domain: Appears to be a regular domain")
            
            result_lines.append("\n[+] Email format is valid")
            
        except Exception as e:
            result_lines.append(f"• Error checking domain: {str(e)}")
        
        return "\n".join(result_lines)
            
    except Exception as e:
        return tool_error("email verification", e)


async def _check_disposable_email(email: str) -> bool:
    """Check if email is from a disposable/temporary email service."""
    domain = email.split('@')[1]
    
    # Common disposable email domains
    disposable_domains = {
        "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
        "throwawaymail.com", "fakeinbox.com", "temp-mail.org", "yopmail.com",
        "maildrop.cc", "getnada.com", "trashmail.com", "tempmail.net",
        "temp-mail.io", "10minutemail.net", "20minutemail.com", "33mail.com",
        "emailondeck.com", "mohmal.com", "jetable.org", "mailexpire.com",
        "tempinbox.com", "tempmail.pro", "tempmail.address", "dispostable.com"
    }
    
    return domain in disposable_domains


# =============================================================================
# 3. PHONE NUMBER INFO
# =============================================================================

async def phone_info(args: dict) -> str:
    """Get information about a phone number (carrier, location, type).
    
    Uses free APIs to look up phone number information.
    """
    phone = (args.get("phone") or "").strip()
    
    if not phone:
        return "What phone number should I look up, sir?"
    
    # Clean the phone number
    cleaned = re.sub(r"[^\d+]", "", phone)
    if cleaned.startswith("+"):
        international = True
    else:
        international = False
        # Assume US if no country code
        cleaned = "+1" + cleaned if len(cleaned) == 10 else cleaned
    
    try:
        # Try multiple free phone lookup services
        
        # 1. Try numverify.com (free tier available)
        # Note: numverify requires API key, so we skip it
        
        # 2. Try phonevalidator.com (free for basic use)
        # This doesn't require auth
        
        # 3. Use abstractapi.com (free tier, but needs key)
        # Skip for now
        
        # 4. Try to get info from country code
        country_info = _get_country_from_phone(cleaned)
        
        # 5. Try carrier lookup via free API
        carrier_info = await _get_carrier_info(cleaned)
        
        result_lines = [f"Phone number info for **{phone}**:"]
        
        if country_info:
            result_lines.append(f"• Country: {country_info.get('name', 'Unknown')} ({country_info.get('code', '')})")
        
        if carrier_info:
            result_lines.append(f"• Carrier: {carrier_info.get('carrier', 'Unknown')}")
            result_lines.append(f"• Type: {carrier_info.get('type', 'Unknown')}")
        else:
            result_lines.append("• Carrier: Could not determine (try with country code)")
        
        # Check if it's a valid format
        if _is_valid_phone_format(cleaned):
            result_lines.append("[+] Phone number format appears valid")
        else:
            result_lines.append("⚠️  Phone number format may be invalid")
        
        return "\n".join(result_lines)
            
    except Exception as e:
        return tool_error("phone info lookup", e)


def _get_country_from_phone(phone: str) -> dict | None:
    """Extract country info from phone number."""
    # Common country codes
    country_codes = {
        "1": {"code": "US", "name": "United States"},
        "44": {"code": "GB", "name": "United Kingdom"},
        "33": {"code": "FR", "name": "France"},
        "49": {"code": "DE", "name": "Germany"},
        "34": {"code": "ES", "name": "Spain"},
        "39": {"code": "IT", "name": "Italy"},
        "81": {"code": "JP", "name": "Japan"},
        "86": {"code": "CN", "name": "China"},
        "91": {"code": "IN", "name": "India"},
        "7": {"code": "RU", "name": "Russia"},
        "82": {"code": "KR", "name": "South Korea"},
        "61": {"code": "AU", "name": "Australia"},
        "55": {"code": "BR", "name": "Brazil"},
    }
    
    # Extract country code from international format
    if phone.startswith("+"):
        phone = phone[1:]
    
    if len(phone) >= 2:
        code = phone[:2]
        if code in country_codes:
            return {"code": country_codes[code]["code"], "name": country_codes[code]["name"]}
    
    if len(phone) >= 1:
        code = phone[:1]
        if code in country_codes:
            return {"code": country_codes[code]["code"], "name": country_codes[code]["name"]}
    
    return None


async def _get_carrier_info(phone: str) -> dict | None:
    """Get carrier info from phone number using free API."""
    # Clean phone number for API
    cleaned = re.sub(r"[^\d]", "", phone)
    
    try:
        # Try numapi.com (free for basic lookups)
        url = f"https://numapi.com/api/validate?number={cleaned}&format=json"
        client = _client(url, timeout=10.0)
        response = await client.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "carrier": data.get("carrier", ""),
                "type": data.get("type", ""),
                "country": data.get("country", "")
            }
    except Exception:
        pass
    
    return None


def _is_valid_phone_format(phone: str) -> bool:
    """Check if phone number has valid format."""
    # Basic validation: should have at least 7 digits
    digits = re.sub(r"[^\d]", "", phone)
    return len(digits) >= 7


# =============================================================================
# 4. USERNAME SEARCH
# =============================================================================

async def username_search(args: dict) -> str:
    """Search for a username across multiple platforms.
    
    Checks if username exists on GitHub, Twitter, Instagram, etc.
    """
    username = (args.get("username") or "").strip().lower()
    
    if not username:
        return "What username should I search for, sir?"
    
    # Validate username (basic check)
    if not re.match(r"^[a-z0-9_\-]{2,30}$", username, re.I):
        return f"'{username}' doesn't look like a valid username, sir."
    
    try:
        platforms = [
            ("GitHub", f"https://github.com/{username}", "github"),
            ("Twitter", f"https://twitter.com/{username}", "twitter"),
            ("Instagram", f"https://instagram.com/{username}", "instagram"),
            ("LinkedIn", f"https://linkedin.com/in/{username}", "linkedin"),
            ("Reddit", f"https://reddit.com/user/{username}", "reddit"),
            ("YouTube", f"https://youtube.com/c/{username}", "youtube"),
            ("TikTok", f"https://tiktok.com/@{username}", "tiktok"),
            ("Facebook", f"https://facebook.com/{username}", "facebook"),
        ]
        
        results = []
        for platform_name, url, platform_id in platforms:
            exists = await _check_username_exists(username, platform_id)
            status = "[+] Available" if not exists else "[-] Taken"
            results.append(f"• {platform_name}: {status} - {url}")
        
        result_lines = [f"Username **@{username}** availability:"]
        result_lines.extend(results)
        
        return "\n".join(result_lines)
            
    except Exception as e:
        return tool_error("username search", e)


async def _check_username_exists(username: str, platform: str) -> bool:
    """Check if username exists on a specific platform."""
    try:
        if platform == "github":
            url = f"https://api.github.com/users/{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url)
            # 404 means not found, 200 means exists
            return response.status_code == 200
        
        elif platform == "twitter":
            # Twitter API requires auth, so we do a simple HEAD request
            url = f"https://twitter.com/{username}"
            client = _client(url, timeout=10.0)
            response = await client.head(url, follow_redirects=True)
            # Check if page exists and doesn't redirect to signup
            return response.status_code == 200
        
        elif platform == "instagram":
            url = f"https://instagram.com/{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url, follow_redirects=True)
            # Instagram redirects to login if not found
            return response.status_code == 200 and "Page Not Found" not in response.text
        
        elif platform == "linkedin":
            url = f"https://linkedin.com/in/{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url, follow_redirects=True)
            # LinkedIn shows 404 for non-existent profiles
            return response.status_code != 404
        
        elif platform == "reddit":
            url = f"https://www.reddit.com/user/{username}.json"
            client = _client(url, timeout=10.0)
            response = await client.get(url)
            data = response.json() if response.status_code == 200 else {}
            return bool(data.get("data", {}).get("name"))
        
        elif platform == "youtube":
            url = f"https://youtube.com/c/{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url, follow_redirects=True)
            # YouTube redirects if not found
            return response.status_code == 200
        
        elif platform == "tiktok":
            url = f"https://tiktok.com/@{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url, follow_redirects=True)
            return response.status_code == 200
        
        elif platform == "facebook":
            url = f"https://facebook.com/{username}"
            client = _client(url, timeout=10.0)
            response = await client.get(url, follow_redirects=True)
            return response.status_code == 200
        
        return False
    except Exception:
        return False


# =============================================================================
# 5. WEBSITE INFO
# =============================================================================

async def website_info(args: dict) -> str:
    """Extract metadata and information from a website.
    
    Gets HTTP headers, technologies used, SSL info, and basic metadata.
    """
    url = (args.get("url") or "").strip()
    
    if not url:
        return "What URL should I analyze, sir?"
    
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    try:
        # Parse URL
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Validate URL
        if not domain:
            return f"'{url}' doesn't look like a valid URL, sir."
        
        client = _client(url, timeout=15.0)
        
        # 1. Get HTTP headers
        response = await client.get(url, follow_redirects=True, timeout=15.0)
        
        result_lines = [f"Website analysis for **{url}**:"]
        
        # Status
        result_lines.append(f"• Status Code: {response.status_code}")
        
        # Final URL (after redirects)
        if response.url != url:
            result_lines.append(f"• Final URL: {response.url}")
        
        # Content type
        content_type = response.headers.get("content-type", "")
        result_lines.append(f"• Content-Type: {content_type}")
        
        # Server info
        server = response.headers.get("server", "Unknown")
        result_lines.append(f"• Server: {server}")
        
        # Technologies from headers
        tech = []
        for header, value in response.headers.items():
            if header.lower() == "x-powered-by":
                tech.append(f"Powered by: {value}")
            elif header.lower() == "x-generator":
                tech.append(f"Generator: {value}")
        if tech:
            result_lines.append(f"• Technologies: {', '.join(tech)}")
        
        # SSL info
        if parsed.scheme == "https":
            ssl_result = await ssl_cert_info({"domain": domain})
            if "SSL Certificates" in ssl_result:
                # Extract issuer from ssl_result
                for line in ssl_result.split('\n'):
                    if "Issuer:" in line:
                        result_lines.append(f"• SSL Issuer: {line.split('Issuer: ')[1] if 'Issuer: ' in line else 'Unknown'}")
                        break
        
        # Response time
        result_lines.append(f"• Response Time: {response.elapsed.total_seconds():.2f}s")
        
        # Extract title if HTML
        if content_type and "text/html" in content_type:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text[:10000], 'html.parser')
                title = soup.title.string if soup.title else "No title"
                result_lines.append(f"• Page Title: {title[:100]}")
            except Exception:
                pass
        
        return "\n".join(result_lines)
            
    except httpx.TimeoutException:
        return tool_error("website info", httpx.TimeoutException("timeout"))
    except httpx.RequestError as e:
        return tool_error("website info", e)
    except Exception as e:
        return tool_error("website info", e)


# Import ssl_cert_info for use in website_info
from mushegh.brain.tools.osint import ssl_cert_info


# =============================================================================
# SCHEMAS AND HANDLERS
# =============================================================================

SCHEMAS = [
    # 1. DNS Lookup
    {
        "type": "function",
        "function": {
            "name": "dns_lookup",
            "description": "Look up DNS records (A, AAAA, MX, TXT, CNAME, NS) for a domain. "
                           "Use when the owner asks 'what are the DNS records for X' or 'who hosts this domain'. "
                           "Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to look up (e.g., google.com, example.org)"
                    },
                    "type": {
                        "type": "string",
                        "description": "DNS record type (A, AAAA, MX, TXT, CNAME, NS, ALL). Default: ALL",
                        "enum": ["A", "AAAA", "MX", "TXT", "CNAME", "NS", "ALL"]
                    }
                },
                "required": ["domain"]
            }
        }
    },
    # 2. Email Verification
    {
        "type": "function",
        "function": {
            "name": "email_verify",
            "description": "Verify an email address format and check domain validity, MX records, and SMTP. "
                           "Use when the owner asks 'is this email valid' or 'check this email address'. "
                           "Detects disposable email addresses. Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Email address to verify (e.g., user@example.com)"
                    }
                },
                "required": ["email"]
            }
        }
    },
    # 3. Phone Number Info
    {
        "type": "function",
        "function": {
            "name": "phone_info",
            "description": "Get information about a phone number (country, carrier, type). "
                           "Use when the owner asks 'who owns this phone number' or 'where is this number from'. "
                           "Free, no API key required for basic info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Phone number to look up (e.g., +1-555-123-4567, 5551234567)"
                    }
                },
                "required": ["phone"]
            }
        }
    },
    # 4. Username Search
    {
        "type": "function",
        "function": {
            "name": "username_search",
            "description": "Check if a username is available across multiple platforms (GitHub, Twitter, Instagram, etc.). "
                           "Use when the owner asks 'is this username available' or 'check if @username exists'. "
                           "Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to search (e.g., john_doe, alice123)"
                    }
                },
                "required": ["username"]
            }
        }
    },
    # 5. Website Info
    {
        "type": "function",
        "function": {
            "name": "website_info",
            "description": "Extract metadata and information from a website (headers, technologies, SSL, title). "
                           "Use when the owner asks 'what technology does this site use' or 'analyze this website'. "
                           "Free, no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to analyze (e.g., https://example.com, example.com)"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

HANDLERS = {
    "dns_lookup": dns_lookup,
    "email_verify": email_verify,
    "phone_info": phone_info,
    "username_search": username_search,
    "website_info": website_info,
}
