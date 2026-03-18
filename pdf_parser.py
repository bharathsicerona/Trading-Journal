"""
PDF Parser Module for Trading Automation

This version adds broker-specific parsing functions and a dispatcher so Groww,
mStock and Exness layouts are handled with tailored logic and fall back to
a robust generic parser when needed.

Key features:
- _normalize_number: robust numeric normalization
- extract_text_from_pdf: safe PDF text extraction
- parse_trades_generic: improved, heuristic generic parser
- parse_trades_groww / parse_trades_mstock / parse_trades_exness: broker
  specific parsers that attempt to handle known layout differences
- parse_trades: public dispatcher that picks the best parser based on the
  broker argument and text heuristics
- Other extractors (funds, pledges, summary) unchanged but using numeric
  normalization for robustness.

Notes:
- These parser implementations are defensive: they try multiple strategies
  and log warnings rather than raising on parse failures. If you have sample
  PDF text for each broker, we can further tune the regexes for 100% accuracy.
"""

import pdfplumber
import re
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Numeric regexes
NUMBER_RE = re.compile(r'(-?\(?\$?\s?[\d,]+(?:\.\d+)?\)?(?:\s*(?:Cr|Dr|CR|DR))?)')
INT_FLOAT_RE = re.compile(r'(-?\(?\$?\s?[\d,]+(?:\.\d+)?\)?(?:\s*(?:Cr|Dr|CR|DR))?)')


def _normalize_number(num_str: str) -> Optional[float]:
    """Normalize a numeric string to float.

    Handles: 1,234.56  (1,234.56)  $1,234  1000
    Returns None if it cannot be parsed.
    """
    if not num_str:
        return None
    s = str(num_str).strip()

    # Remove currency symbols and words
    s = s.replace('$', '')
    s = s.replace('₹', '')
    s = s.replace('INR', '')
    s = s.replace('USD', '')
    s = s.strip()

    negative = False
    if s.startswith('(') and s.endswith(')'):
        negative = True
        s = s[1:-1].strip()
        
    if s.lower().endswith('dr'):
        negative = True
        s = s[:-2].strip()
    elif s.lower().endswith('cr'):
        s = s[:-2].strip()

    s = s.replace('+', '')
    s = s.replace(',', '')

    if s == '':
        return None

    try:
        v = float(s)
        return -v if negative else v
    except ValueError:
        logger.debug(f"Failed to normalize number '{num_str}' -> '{s}'")
        return None


def extract_text_from_pdf(pdf_path: str, password: Optional[str] = None) -> str:
    """Extract all text from a PDF file with error handling.

    When password is None it will call pdfplumber.open(pdf_path) (keeps
    compatibility with tests/mocks that expect a single-arg call).
    """
    try:
        if password is None:
            opener = lambda p: pdfplumber.open(p)
        else:
            opener = lambda p: pdfplumber.open(p, password=password)

        with opener(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                pg_text = page.extract_text()
                if pg_text:
                    text += pg_text + "\n"
            return text.strip()
    except Exception as e:
        error_msg = str(e) or repr(e)
        if "Password" in error_msg or "encrypt" in error_msg.lower() or "PDFPasswordIncorrect" in repr(e):
            logger.error(f"Error extracting text from {pdf_path}: Incorrect password or PDF is encrypted.")
        else:
            logger.error(f"Error extracting text from {pdf_path}: {error_msg}")
        return ""


# ------------------ Generic trade parser (robust heuristics) ------------------
def parse_trades_generic(text: str, trade_date: datetime.date, broker: str = 'Unknown') -> List[Dict[str, Any]]:
    """Generic, heuristic-based trade parser.

    This parser attempts to handle many tabular forms by locating numeric tokens
    and keywords in each line. It is forgiving and skips malformed lines.
    """
    trades: List[Dict[str, Any]] = []
    lines = text.split('\n')
    in_trades_section = False

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue

        # Start of trades section heuristic
        if re.search(r'Buy\s*\(B\)\/Sell\s*\(S\)', line, re.IGNORECASE) or re.search(r'Contract Note|Trade Details', line, re.IGNORECASE):
            in_trades_section = True
            logger.debug(f"Generic parser: found trades header at line {i}")
            continue

        # End section heuristics
        if in_trades_section and re.search(r'Future|Options|Positions|Summary|Total|Sub-total|Charges|Levies|Tax', line, re.IGNORECASE):
            in_trades_section = False
            logger.debug(f"Generic parser: found end-of-trades marker at line {i}")
            continue

        # If not in a section, still try to parse lines that look like trades
        consider = in_trades_section or re.search(r'\b(NSE|BSE)\b', line) or re.search(r'\b(Buy|Sell|B|S)\b', line, re.IGNORECASE)
        if not consider:
            continue

        try:
            # Find all numeric tokens (strike, qty, prices, totals)
            raw_numbers = INT_FLOAT_RE.findall(line)
            nums = [(_normalize_number(n) if n else None) for n in raw_numbers]
            nums = [n for n in nums if n is not None]

            # Basic requirement: at least 2 numeric values (qty and net total)
            if len(nums) < 2:
                logger.debug(f"Generic parser: skipping line {i} insufficient numeric tokens: '{line}'")
                continue

            # Strike detection: first numeric that looks like a price/strike (not year)
            strike = None
            for n in nums:
                if n is not None and n > 0 and n < 1e6 and not (1900 <= n <= 2100):
                    strike = n
                    break

            # quantity detection: prefer numeric immediately after Buy/Sell token in the text tokens
            qty = None
            tokens = line.split()
            bs_idx = None
            for idx, t in enumerate(tokens):
                if re.fullmatch(r'(?i)(buy|sell|b|s)', t):
                    bs_idx = idx
                    break
            if bs_idx is not None and bs_idx + 1 < len(tokens):
                try:
                    candidate = _normalize_number(tokens[bs_idx + 1])
                    if candidate is not None and float(candidate).is_integer() and 0 < candidate < 1e6:
                        qty = int(candidate)
                except Exception:
                    qty = None

            # Fallback: first integer-like numeric that's not strike
            if qty is None:
                for n in nums:
                    if n is None:
                        continue
                    if strike is not None and abs(n - strike) < 0.0001:
                        continue
                    if float(n).is_integer() and 0 < n < 1e6:
                        qty = int(n)
                        break

            # net total: assume last numeric token
            net_total = nums[-1]

            # net price: second last numeric if available
            net_price = nums[-2] if len(nums) >= 2 else None

            # WAP: try to find numeric immediately after qty token in the text tokens
            wap = None
            tokens = line.split()
            if qty is not None:
                for idx, t in enumerate(tokens):
                    try:
                        if _normalize_number(t) == qty or t.replace(',', '') == str(qty):
                            if idx + 1 < len(tokens):
                                cand = _normalize_number(tokens[idx + 1])
                                if cand is not None:
                                    wap = cand
                                    break
                    except Exception:
                        continue
            if wap is None and len(nums) >= 2:
                wap = nums[1]

            # Exchange and underlying
            exchange = 'UNKNOWN'
            m = re.search(r'\b(NSE|BSE)\b', line)
            if m:
                exchange = m.group(1)
            underlying = None
            try:
                if exchange != 'UNKNOWN':
                    toks = line.split()
                    idx = toks.index(exchange)
                    if idx + 1 < len(toks):
                        underlying = toks[idx + 1]
            except Exception:
                underlying = None

            # Option type
            option_type = None
            mtype = re.search(r'\b(CE|PE|Call|Put)\b', line, re.IGNORECASE)
            if mtype:
                option_type = mtype.group(1).upper()

            # Buy/Sell
            bs = None
            if re.search(r'\bBuy\b', line, re.IGNORECASE) or re.search(r'\bB\b', line):
                bs = 'B'
            elif re.search(r'\bSell\b', line, re.IGNORECASE) or re.search(r'\bS\b', line):
                bs = 'S'

            trade = {
                'Date': trade_date,
                'Exchange': exchange,
                'Underlying': underlying or 'UNKNOWN',
                'Strike': strike,
                'Type': option_type or 'UNKNOWN',
                'Expiry': None,
                'Buy/Sell': bs,
                'Quantity': qty,
                'WAP': wap,
                'Brokerage': None,
                'Net Price': net_price,
                'Net Total': net_total,
                'Broker': broker
            }

            trades.append(trade)
        except Exception as e:
            logger.exception(f"Generic parser: unexpected error parsing line {i}: {e}")
            continue

    logger.info(f"Generic parser: parsed {len(trades)} trades")
    return trades


# ------------------ Broker-specific parsers ----------------------------------
def parse_trades_groww(text: str, trade_date: datetime.date, broker: str = 'Groww') -> List[Dict[str, Any]]:
    """Parser tailored for Groww-like contract notes.

    Groww often prints 'Buy'/'Sell' as words, underlying name, strike, option
    type (CE/PE), expiry in 'DD MMM YYYY' and numeric columns for qty, wap,
    brokerage, net price and net total. We'll use regex patterns tuned to that.

    This function falls back to generic parser on ambiguous lines.
    """
    trades = []
    lines = text.split('\n')

    # Typical Groww trade line example (space-separated tokens):
    # RELIANCE 2500 CE 20 Jan 2024 Buy 10 250.50 5.00 255.50 2555.00

    pattern = re.compile(r"(?P<underlying>.+?)\s+(?P<strike>\d{1,5}(?:\.\d+)?)\s+(?P<otype>CE|PE|Call|Put)\s+(?P<expiry>\d{1,2}\s+\w{3}\s+\d{4})\s+(?P<bs>Buy|Sell|B|S)\s+(?P<qty>-?\d+).*?(?P<rest>.*)", re.IGNORECASE)

    for i, line in enumerate(lines):
        if "Annexure A" in line:
            break  # Stop parsing at Annexure
        line = line.strip()
        if not line:
            continue
        m = pattern.search(line)
        if not m:
            continue
        try:
            underlying = m.group('underlying')
            strike = _normalize_number(m.group('strike'))
            otype = m.group('otype').upper()
            try:
                expiry = datetime.strptime(m.group('expiry'), '%d %b %Y').date()
            except Exception:
                expiry = None
            bs_token = m.group('bs')
            bs = 'B' if re.search(r'Buy|B', bs_token, re.IGNORECASE) else 'S'
            qty = int(m.group('qty'))

            # Extract remaining numeric tokens from rest of line
            rest = m.group('rest')
            nums = [(_normalize_number(n) if n else None) for n in INT_FLOAT_RE.findall(rest)]
            nums = [n for n in nums if n is not None]

            # Expecting [wap, brokerage, net_price, net_total] or similar
            wap = nums[0] if len(nums) >= 1 else None
            brokerage = nums[1] if len(nums) >= 2 else None
            net_price = nums[2] if len(nums) >= 3 else None
            net_total = nums[3] if len(nums) >= 4 else (nums[-1] if nums else None)

            trade = {
                'Date': trade_date,
                'Exchange': 'NSE',
                'Underlying': underlying,
                'Strike': strike,
                'Type': otype,
                'Expiry': expiry,
                'Buy/Sell': bs,
                'Quantity': qty,
                'WAP': wap,
                'Brokerage': brokerage,
                'Net Price': net_price,
                'Net Total': net_total,
                'Broker': broker
            }
            trades.append(trade)
        except Exception as e:
            logger.exception(f"Groww parser: error parsing line {i}: {e}")
            continue

    if not trades:
        # Fall back to generic parser
        logger.info("Groww parser: no trades found using Groww patterns, falling back to generic parser")
        return parse_trades_generic(text, trade_date, broker)

    logger.info(f"Groww parser: parsed {len(trades)} trades")
    return trades


def parse_trades_mstock(text: str, trade_date: datetime.date, broker: str = 'mStock') -> List[Dict[str, Any]]:
    """Parser for mStock / Comm_contract style notes (exchange-prefixed lines).

    Example typical line (space-separated):
    NSE RELIANCE 2500 CE 20 Jan 2024 B 10 250.50 5.00 255.50 2555.00
    """
    trades = []
    lines = text.split('\n')

    # Detailed derivative format pattern: 
    # OPTIDX NIFTY 17MAR26 23350.00 CE (BT) B 260 0.0000 90.0000 0.0192 90.0192 0.0000-23405.0000NSEFO
    new_format_re = re.compile(
        r"^(?:OPTIDX|OPTSTK)\s+(?P<underlying>.+?)\s+(?P<expiry>\d{2}[A-Za-z]{3}\d{2})\s+"
        r"(?P<strike>\d+(?:\.\d+)?)\s+(?P<otype>CE|PE|Call|Put).*?\s+"
        r"(?P<bs>B|Buy|S|Sell)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<rest>.*)", re.IGNORECASE
    )

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
            
        # Try detailed format first
        m_new = new_format_re.match(line)
        if m_new:
            try:
                underlying = m_new.group('underlying').strip()
                strike = _normalize_number(m_new.group('strike'))
                otype = 'CE' if m_new.group('otype').upper().startswith('C') else 'PE'
                try:
                    expiry = datetime.strptime(m_new.group('expiry').upper(), '%d%b%y').date()
                except Exception:
                    expiry = None
                
                bs = 'B' if m_new.group('bs').upper().startswith('B') else 'S'
                qty = int(float(m_new.group('qty')))
                
                rest = m_new.group('rest')
                exchange = 'NSE' if 'NSE' in rest.upper() else ('BSE' if 'BSE' in rest.upper() else 'UNKNOWN')
                
                # The regex natively handles extracting squished negatives like "0.0000-23405.0000NSEFO"
                nums = [(_normalize_number(n) if n else None) for n in INT_FLOAT_RE.findall(rest)]
                nums = [n for n in nums if n is not None]
                
                trade = {
                    'Date': trade_date,
                    'Exchange': exchange,
                    'Underlying': underlying,
                    'Strike': strike,
                    'Type': otype,
                    'Expiry': expiry,
                    'Buy/Sell': bs,
                    'Quantity': qty,
                    'WAP': nums[1] if len(nums) >= 2 else None,
                    'Brokerage': nums[2] if len(nums) >= 3 else None,
                    'Net Price': nums[3] if len(nums) >= 4 else None,
                    'Net Total': nums[-1] if nums else None,
                    'Broker': broker
                }
                trades.append(trade)
                continue
            except Exception as e:
                logger.debug(f"mStock parser: failed on new format line {i} '{line}': {e}")

        # Look for lines that start with exchange token
        if not re.match(r'^(NSE|BSE)\b', line):
            continue
        parts = line.split()
        
        # Handle underlying with space (e.g. NIFTY BANK) by merging parts if they aren't numbers
        # This is a heuristic: strike is usually the first numeric part after the exchange
        strike_idx = 2
        for idx, part in enumerate(parts[1:], start=1):
            if re.match(r'^\d{1,5}(?:\.\d+)?$', part):
                strike_idx = idx
                break
        parts = [parts[0], " ".join(parts[1:strike_idx])] + parts[strike_idx:]
        
        try:
            if len(parts) < 8:
                logger.debug(f"mStock parser: skipping short line {i}: '{line}'")
                continue
            exchange = parts[0]
            underlying = parts[1]
            strike = _normalize_number(parts[2])
            otype = parts[3]

            # expiry might be 3 tokens
            expiry = None
            expiry_candidate = ' '.join(parts[4:7])
            try:
                expiry = datetime.strptime(expiry_candidate, '%d %b %Y').date()
                rest_idx = 7
            except Exception:
                # Try two-token expiry
                try:
                    expiry = datetime.strptime(parts[4], '%d-%b-%Y').date()
                    rest_idx = 5
                except Exception:
                    expiry = None
                    rest_idx = 5

            # Buy/Sell token next
            bs = parts[rest_idx]
            qty = None
            wap = None
            brokerage = None
            net_price = None
            net_total = None

            # Remaining numeric fields
            remaining = parts[rest_idx + 1:]
            nums = [(_normalize_number(n) if n else None) for n in remaining]
            nums = [n for n in nums if n is not None]

            # Heuristics mapping (qty, wap, brokerage, net_price, net_total)
            if nums:
                # qty is first integer-like value
                for n in nums:
                    if float(n).is_integer() and n > 0 and n < 1e6:
                        qty = int(n)
                        break
                # net_total likely last
                net_total = nums[-1]
                # net_price likely second-last
                net_price = nums[-2] if len(nums) >= 2 else None
                # wap likely immediately after qty, otherwise nums[1]
                if qty is not None:
                    try:
                        qpos = nums.index(float(qty))
                        if qpos + 1 < len(nums):
                            wap = nums[qpos + 1]
                    except Exception:
                        if len(nums) >= 2:
                            wap = nums[1]

            trade = {
                'Date': trade_date,
                'Exchange': exchange,
                'Underlying': underlying,
                'Strike': strike,
                'Type': otype,
                'Expiry': expiry,
                'Buy/Sell': 'B' if re.search(r'B|Buy', bs, re.IGNORECASE) else 'S',
                'Quantity': qty,
                'WAP': wap,
                'Brokerage': brokerage,
                'Net Price': net_price,
                'Net Total': net_total,
                'Broker': broker
            }
            trades.append(trade)
        except Exception as e:
            logger.exception(f"mStock parser: error parsing line {i}: {e}")
            continue

    if not trades:
        logger.info("mStock parser: falling back to generic parser")
        return parse_trades_generic(text, trade_date, broker)

    logger.info(f"mStock parser: parsed {len(trades)} trades")
    return trades


def parse_trades_exness(text: str, trade_date: datetime.date, broker: str = 'Exness') -> List[Dict[str, Any]]:
    """Parser for Exness-style statements.

    Exness often uses different currency and layout; many Exness PDFs may be
    fund-related rather than option trades. This parser looks for lines with
    recognizable patterns and otherwise falls back to generic parsing.
    """
    trades = []
    lines = text.split('\n')

    # Look for lines with 'Lot' or 'Volume' or forex pairs
    pair_re = re.compile(r'([A-Z]{3,6}[/-]?[A-Z]{3,6})')

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue

        # Try to parse forex-like lines: Pair Side Volume Price P/L
        # Example: EUR/USD Buy 0.10 1.23456 10.50
        m = re.search(r'([A-Z]{3,6}[/-]?[A-Z]{3,6})\s+(Buy|Sell)\s+(\d+\.?\d*)\s+(\d+\.\d+)\s+(-?\d+\.?\d*)', line)
        if m:
            try:
                underlying = m.group(1)
                bs = 'B' if m.group(2).lower().startswith('b') else 'S'
                qty = float(m.group(3))
                wap = _normalize_number(m.group(4))
                pnl = _normalize_number(m.group(5))
                trade = {
                    'Date': trade_date,
                    'Exchange': 'FOREX',
                    'Underlying': underlying,
                    'Strike': None,
                    'Type': 'FX',
                    'Expiry': None,
                    'Buy/Sell': bs,
                    'Quantity': qty,
                    'WAP': wap,
                    'Brokerage': None,
                    'Net Price': None,
                    'Net Total': pnl,
                    'Broker': broker
                }
                trades.append(trade)
                continue
            except Exception as e:
                logger.debug(f"Exness parser: forex pattern match failed on line {i}: {e}")

        # Fallback: attempt generic parse for Exness lines
        # collect numeric tokens and try to map them
        # Use generic parser as fallback
    if not trades:
        logger.info("Exness parser: falling back to generic parser")
        return parse_trades_generic(text, trade_date, broker)

    logger.info(f"Exness parser: parsed {len(trades)} trades")
    return trades


# ------------------ Dispatcher ------------------------------------------------
def parse_trades(text: str, trade_date: datetime.date, broker: str = 'Unknown') -> List[Dict[str, Any]]:
    """Main entrypoint for parsing trades. Chooses broker-specific parser where possible.

    Priority: explicit broker argument -> text-based detection -> generic
    """
    b = (broker or '').strip().lower()

    # If explicit broker provided, prefer it
    if 'groww' in b:
        return parse_trades_groww(text, trade_date, broker='Groww')
    if 'mstock' in b or 'm-stock' in b or 'm stock' in b or 'mstock' == b:
        return parse_trades_mstock(text, trade_date, broker='mStock')
    if 'exness' in b:
        return parse_trades_exness(text, trade_date, broker='Exness')

    # Text-based detection
    txt = (text or '').lower()
    if 'groww' in txt or 'groww.in' in txt:
        return parse_trades_groww(text, trade_date, broker='Groww')
    if 'mstock' in txt or 'm-stock' in txt or 'comm_contract' in txt:
        return parse_trades_mstock(text, trade_date, broker='mStock')
    if 'exness' in txt:
        return parse_trades_exness(text, trade_date, broker='Exness')

    # Default generic parser
    return parse_trades_generic(text, trade_date, broker)


# ------------------ Other extractors (unchanged but robust) -------------------

def extract_trade_date(text: str) -> Optional[datetime.date]:
    """Extract trade date from PDF text"""
    match = re.search(r'Trade Date[:\s]*([\d]{1,2}[\-/\.][\d]{1,2}[\-/\.][\d]{2,4})', text)
    if match:
        ds = match.group(1)
        for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y'):
            try:
                return datetime.strptime(ds, fmt).date()
            except Exception:
                continue
    generic = re.search(r'([\d]{1,2}[\s\-\/\.][A-Za-z]{3,9}[\s\-\/\.][\d]{2,4})', text)
    if generic:
        ds = generic.group(1)
        for fmt in ('%d %b %Y', '%d %B %Y', '%d-%b-%Y', '%d/%b/%Y'):
            try:
                return datetime.strptime(ds.replace('-', ' ').replace('/', ' ').replace('.', ' '), fmt).date()
            except Exception:
                continue
                
    # Fallback: pure numeric date anywhere in the text (e.g. 17/03/2026)
    generic_num = re.search(r'\b(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})\b', text)
    if generic_num:
        ds = generic_num.group(1)
        for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y'):
            try:
                return datetime.strptime(ds, fmt).date()
            except Exception:
                continue
                
    return None


def extract_funds_data(text: str, trade_date: datetime.date, broker: str) -> List[Dict[str, Any]]:
    """Extract deposit/withdrawal information from PDF text"""
    funds: List[Dict[str, Any]] = []
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Pay In / Pay Out
        if 'Pay In' in line or 'Pay Out' in line or 'Pay In / Pay Out Obligation' in line:
            m = NUMBER_RE.search(line)
            if m:
                amount = _normalize_number(m.group(1))
                if amount is not None and amount != 0:
                    funds.append({
                        'Date': trade_date,
                        'Broker': broker,
                        'Type': 'Deposit' if amount > 0 else 'Withdrawal',
                        'Amount': abs(amount),
                        'Currency': 'USD' if 'exness' in (broker or '').lower() else 'INR',
                        'Description': line[:200]
                    })
        # Net Amount
        if 'Net Amount Receivable' in line or 'Net Amount Payable' in line or 'Net Amount' in line:
            m = NUMBER_RE.search(line)
            if m:
                amount = _normalize_number(m.group(1))
                if amount is not None and amount != 0:
                    funds.append({
                        'Date': trade_date,
                        'Broker': broker,
                        'Type': 'Settlement Payable' if amount < 0 else 'Settlement Receivable',
                        'Amount': abs(amount),
                        'Currency': 'USD' if 'exness' in (broker or '').lower() else 'INR',
                        'Description': 'Final Settlement Amount'
                    })
    return funds


def extract_pledges_data(text: str, trade_date: datetime.date, broker: str) -> List[Dict[str, Any]]:
    """Extract pledge/collateral information from PDF text"""
    pledges: List[Dict[str, Any]] = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(kw in line.lower() for kw in ['pledge', 'collateral', 'margin', 'haircut', 'utilised', 'utilized']):
            m = NUMBER_RE.search(line)
            if m:
                amount = _normalize_number(m.group(1))
                if amount is not None:
                    pledges.append({
                        'Date': trade_date,
                        'Broker': broker,
                        'Amount': abs(amount),
                        'Description': line[:200]
                    })
    return pledges


def extract_account_summary(text: str, trade_date: datetime.date, broker: str, filename: str) -> Dict[str, Any]:
    """Extract account-level summary from PDF text"""
    summary: Dict[str, Any] = {
        'Date': trade_date,
        'Broker': broker,
        'Filename': filename,
        'Total_Trades': 0,
        'Total_Fees': 0.0,
        'Settlement_Amount': 0.0,
        'Email_Processed': True
    }

    trade_count = len(re.findall(r'^(?:\s*)(NSE|BSE)\b', text, re.MULTILINE))
    summary['Total_Trades'] = trade_count

    brokerage_lines = re.findall(r'Brokerage.*?(' + INT_FLOAT_RE.pattern + r')', text, flags=re.IGNORECASE)
    fees = 0.0
    for bl in brokerage_lines:
        amt = _normalize_number(bl)
        if amt is not None:
            fees += amt
    summary['Total_Fees'] = fees

    m = re.search(r'Net Amount (?:Receivable|Payable)?.{0,50}(' + INT_FLOAT_RE.pattern + r')', text, flags=re.IGNORECASE)
    if m:
        amt = _normalize_number(m.group(1))
        if amt is not None:
            summary['Settlement_Amount'] = amt

    return summary
