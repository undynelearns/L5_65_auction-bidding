# Issues Found and Fixed — `auction_system.py`

Line numbers refer to the **original** file. Severity: Bandit severity for
Bandit findings; my own rating for the rest. High and medium first.

## Security (Bandit)

| Issue | Type | Line(s) | Description | Fix Approach |
|---|---|---|---|---|
| Jinja2 autoescape disabled (Bandit **B701**, High) | Security / XSS | 65 | `Environment(autoescape=False)` renders the lot title raw, so LOT2's `<script>alert('pwned')</script>` title is injected straight into the HTML. | `Environment(autoescape=True)`. The template is now compiled once at module level. Output shows `&lt;script&gt;...`. |
| Markup built from string concatenation (Bandit **B704**, Medium) | Security / XSS | 70 | `Markup("<span…>" + name + "</span>")` marks untrusted input as safe, so `<img src=x onerror=alert(1)>` executes. | `Markup("<span class='bidder'>{}</span>").format(name)` — `Markup.format` escapes its arguments. |
| Insecure XML-RPC import (Bandit **B411**, High) | Security / XML attacks | 5 | `xmlrpc.client` parses server XML and is vulnerable to entity-expansion / XML-bomb attacks from a malicious or spoofed gateway. | Call `defusedxml.xmlrpc.monkey_patch()` at import time and mark the import `# nosec B411` with the justification. |

## Logic bugs (found by running the program — no tool flags these)

| Issue | Type | Line(s) | Description | Fix Approach |
|---|---|---|---|---|
| Equal bid accepted | Bug (High) | 24 | `amount >= self.highest` lets Ben bid the same 3000 and steal the lead. | Require `amount >= highest + MIN_INCREMENT` once bids exist. |
| `MIN_INCREMENT` never enforced | Bug (High) | 9, 24 | Constant is defined but unused, so a +50 raise is accepted. | Enforced in `place_bid` (same check as above). |
| Seller can bid on own item | Bug (High) | 21–30 | `seller_sam` bids 4000 on his own lot (shill bidding) and wins. | Reject when `bidder == self.seller`. |
| Times compared as strings | Bug (High) | 22 | `"2026-12-01 9:30" > "2026-12-01 18:00"` is True as text (`'9' > '1'`), so a valid 9:30 AM bid is rejected as "closed". | Parse with `datetime.strptime` (`parse_time`) and compare `datetime` objects. |
| Reserve price ignored | Bug (High) | 32–35, 37–38 | Winner and final price are returned even when the highest bid is below the reserve. | `reserve_met()` helper; `winner()` and `final_price()` return `None` if not met. |
| Zero / negative bids accepted | Bug (Medium) | 24 | Rs.0 bid on LOT3 is accepted and `carl` "wins". | Reject `amount <= 0`. |
| Charging with no winner | Bug (Medium) | 72–75 | `chargeWinner` would call the gateway with `None` as the payer. | Return `None` without calling the gateway when there is no winner. |
| Float money arithmetic | Bug (Low) | 38 | `highest * 1.05` can give values like `4200.000000001`; premium is a magic number. | `BUYER_PREMIUM` constant and `round(..., 2)`. |

## Code quality (Pylint)

| Issue | Type | Line(s) | Description | Fix Approach |
|---|---|---|---|---|
| Broad exception raised (**W0719**) | Error handling (Medium) | 23 | `raise Exception("Auction closed")` — callers cannot tell rule violations from real errors. | Custom `BidRejected(ValueError)` exception. |
| Broad exception caught (**W0718**) | Error handling (Medium) | 50 | `except Exception` silently hides every bug (typos, `TypeError`, …) as "bid rejected". | `except (KeyError, BidRejected)` only. |
| Attribute defined outside `__init__` (**W0201**) | Bug risk (Medium) | 27 | `self.leader` only exists after the first bid; `winner()` depends on a length check to avoid `AttributeError`. | `highest` and `leader` became read-only properties derived from `bids`, so state can't get out of sync. |
| Useless `object` inheritance (**R0205**) / too many instance attributes (**R0902**) | Design (Low) | 11 | Python 2 style; 8 attributes. | `@dataclass class Auction:` with 6 fields. |
| Unnecessary `else` after `return`/`continue` (**R1705**, **R1724**) | Style (Low) | 29, 60 | Redundant branches. | Removed; `top_bidders` simplified with `dict.fromkeys` to de-duplicate in order. |
| `len(x) == 0` check (**C1802**) | Style (Low) | 33 | Non-idiomatic emptiness test. | Use truthiness (`if self.bids`). |
| Non-snake_case names (**C0103**) | Naming (Low) | 21, 37, 41, 43, 53, 64, 69, 72, 77, 83 | `placeBid`, `createAuction`, etc. break PEP 8. | Renamed to `place_bid`, `create_auction`, …; global registry renamed `AUCTIONS`. |
| Missing docstrings (**C0114/C0115/C0116**) | Documentation (Low) | 1, 11, all functions | No module/class/function docstrings. | Added docstrings everywhere. |
| Wrong import order (**C0411**) | Style (Low) | 1–6 | Third-party imports before standard library. | Stdlib first, then third-party, in separate groups. |
| `main()` runs on import | Design (Low) | 107 | Importing the module runs the demo. | `if __name__ == "__main__":` guard. |

## Style (Flake8)

| Issue | Type | Line(s) | Description | Fix Approach |
|---|---|---|---|---|
| Expected 2 blank lines (**E302**, **E305**) | PEP 8 formatting | 11, 43, 47, 53, 64, 69, 72, 77, 83, 88, 107 | Top-level definitions separated by only one blank line. | Two blank lines around every top-level `def`/`class`. |
| Line too long (**E501**) | PEP 8 formatting | 66, 89, 90, 93–96, 101 | Lines exceed 79 characters. | Wrapped arguments inside parentheses. |
