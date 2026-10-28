"""Online auction and bidding system.

Tracks AUCTIONS with reserve prices and closing times, accepts bids,
determines the winner and final price (including a buyer's premium),
renders HTML listings safely and charges the winner via a payment gateway.
"""

import json
import time
import xmlrpc.client  # nosec B411
from dataclasses import dataclass, field
from datetime import datetime

from defusedxml.xmlrpc import monkey_patch
from jinja2 import Environment
from markupsafe import Markup

# Protect xmlrpc.client against XML bombs / entity-expansion attacks.
monkey_patch()

PAYMENT_GATEWAY = "https://pay.auction.example/RPC2"
MIN_INCREMENT = 100
BUYER_PREMIUM = 0.05
TIME_FORMAT = "%Y-%m-%d %H:%M"

LISTING_TEMPLATE = Environment(autoescape=True).from_string(
    "<h2>{{ a.title }}</h2><p>Current bid: Rs.{{ a.highest }}</p>"
)


class BidRejected(ValueError):
    """Raised when a bid breaks one of the auction rules."""


def parse_time(value):
    """Convert a 'YYYY-MM-DD HH:MM' string into a datetime."""
    return datetime.strptime(value, TIME_FORMAT)


@dataclass
class Auction:
    """A single auction lot and the bids placed on it."""

    item_id: str
    title: str
    seller: str
    reserve_price: int
    ends_at: datetime
    bids: list = field(default_factory=list)

    @property
    def highest(self):
        """Return the current highest bid amount (0 if no bids)."""
        return self.bids[-1][1] if self.bids else 0

    @property
    def leader(self):
        """Return the current highest bidder (None if no bids)."""
        return self.bids[-1][0] if self.bids else None

    def place_bid(self, bidder, amount, at):
        """Validate and record a bid; raise BidRejected if invalid."""
        if at > self.ends_at:
            raise BidRejected("Auction closed")
        if bidder == self.seller:
            raise BidRejected("Seller cannot bid on own item")
        if amount <= 0:
            raise BidRejected("Bid must be positive")
        if self.bids and amount < self.highest + MIN_INCREMENT:
            raise BidRejected(
                f"Bid must be at least Rs.{self.highest + MIN_INCREMENT}"
            )
        self.bids.append((bidder, amount, at))
        return True

    def reserve_met(self):
        """Return True if the highest bid meets the reserve price."""
        return bool(self.bids) and self.highest >= self.reserve_price

    def winner(self):
        """Return the winning bidder, or None if the reserve was not met."""
        return self.leader if self.reserve_met() else None

    def final_price(self):
        """Return the amount owed by the winner, or None if no winner."""
        if not self.reserve_met():
            return None
        return round(self.highest * (1 + BUYER_PREMIUM), 2)


AUCTIONS = {}


def create_auction(item_id, title, seller, reserve_price, ends_at):
    """Create and register a new auction."""
    AUCTIONS[item_id] = Auction(
        item_id, title, seller, reserve_price, parse_time(ends_at)
    )
    return AUCTIONS[item_id]


def bid(item_id, bidder, amount, at):
    """Place a bid; return True if accepted, False if rejected."""
    try:
        return AUCTIONS[item_id].place_bid(bidder, amount, parse_time(at))
    except (KeyError, BidRejected):
        return False


def top_bidders(item_id, n=3):
    """Return up to n distinct bidders, highest bid first."""
    ordered = sorted(AUCTIONS[item_id].bids, key=lambda b: b[1], reverse=True)
    return list(dict.fromkeys(b[0] for b in ordered))[:n]


def render_listing(item_id):
    """Render an HTML listing with all user data escaped."""
    return LISTING_TEMPLATE.render(a=AUCTIONS[item_id])


def bidder_badge(name):
    """Return an HTML badge; Markup.format escapes the name."""
    return Markup("<span class='bidder'>{}</span>").format(name)


def charge_winner(item_id):
    """Charge the winner through the payment gateway."""
    auction = AUCTIONS[item_id]
    if auction.winner() is None:
        return None
    gateway = xmlrpc.client.ServerProxy(PAYMENT_GATEWAY)
    return gateway.charge(auction.winner(), auction.final_price())


def export_bids(item_id):
    """Export bids as JSON."""
    rows = [
        {"bidder": b[0], "amount": b[1], "at": b[2].strftime(TIME_FORMAT)}
        for b in AUCTIONS[item_id].bids
    ]
    return json.dumps(rows)


def seconds_left(item_id):
    """Return seconds until the auction closes (negative if closed)."""
    return int(AUCTIONS[item_id].ends_at.timestamp() - time.time())


def main():
    """Run a short demo of the auction system."""
    close = "2026-12-01 18:00"
    create_auction("LOT1", "Vintage Camera", "seller_sam", 5000, close)
    create_auction(
        "LOT2", "<script>alert('pwned')</script>Old Radio",
        "seller_ria", 2000, close,
    )
    create_auction("LOT3", "Brass Lamp", "seller_ria", 800, close)
    print("Asha bids 3000:", bid("LOT1", "asha", 3000, "2026-12-01 10:00"))
    print("Ben bids 3000 (same amount):",
          bid("LOT1", "ben", 3000, "2026-12-01 10:05"))
    print("Asha bids 3050 (+50):",
          bid("LOT1", "asha", 3050, "2026-12-01 10:10"))
    print("Seller bids on own item:",
          bid("LOT1", "seller_sam", 4000, "2026-12-01 11:00"))
    print("Bid at 9:30 AM (before 18:00 close):",
          bid("LOT1", "dev", 4500, "2026-12-01 9:30"))
    print("Late bid (next day):",
          bid("LOT1", "eve", 9000, "2026-12-02 09:00"))
    print("Winner (4500 < reserve 5000):", AUCTIONS["LOT1"].winner())
    print("Final price:", AUCTIONS["LOT1"].final_price())
    print("Asha bids 5200:", bid("LOT1", "asha", 5200, "2026-12-01 12:00"))
    print("Winner:", AUCTIONS["LOT1"].winner())
    print("Final price (5200 + 5% premium):", AUCTIONS["LOT1"].final_price())
    print("Top bidders:", top_bidders("LOT1"))
    print("Bids JSON:", export_bids("LOT1"))
    print("Rs.0 bid on LOT3 (reserve 800):",
          bid("LOT3", "carl", 0, "2026-12-01 11:30"))
    print("LOT3 winner:", AUCTIONS["LOT3"].winner())
    print("No-bid winner:", AUCTIONS["LOT2"].winner())
    print("Listing HTML:", render_listing("LOT2"))
    print("Badge:", bidder_badge("<img src=x onerror=alert(1)>"))


if __name__ == "__main__":
    main()
