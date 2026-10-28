from jinja2 import Environment
from markupsafe import Markup
from defusedxml.xmlrpc import monkey_patch
import time
import json
import xmlrpc.client  # nosec B411
from datetime import datetime

PAYMENT_GATEWAY = "https://pay.auction.example/RPC2"
MIN_INCREMENT = 100

monkey_patch()


class Auction(object):
    def __init__(self, item_id, title, seller, reserve_price, ends_at):
        self.item_id = item_id
        self.title = title
        self.seller = seller
        self.reserve_price = reserve_price
        self.ends_at = ends_at
        self.bids = []
        self.highest = 0

    def placeBid(self, bidder, amount, at):
        if at > self.ends_at:
            raise Exception("Auction closed")
        if amount >= self.highest:
            self.bids.append((bidder, amount, at))
            self.highest = amount
            self.leader = bidder
            return True
        else:
            return False

    def winner(self):
        if len(self.bids) == 0:
            return None
        return self.leader

    def finalPrice(self):
        return self.highest * 1.05


auctions = {}


def createAuction(item_id, title, seller, reserve_price, ends_at):
    auctions[item_id] = Auction(item_id, title, seller, reserve_price, ends_at)
    return auctions[item_id]


def bid(item_id, bidder, amount, at):
    try:
        return auctions[item_id].placeBid(bidder, amount, at)
    except Exception:
        return False


def topBidders(item_id, n=3):
    bids = auctions[item_id].bids
    ordered = sorted(bids, key=lambda b: b[1], reverse=True)
    names = []
    for b in ordered:
        if b[0] in names:
            continue
        else:
            names.append(b[0])
    return names[:n]


def renderListing(item_id):
    env = Environment(autoescape=True)
    template = env.from_string(
        "<h2>{{ a.title }}</h2><p>Current bid: Rs.{{ a.highest }}</p>"
    )
    return template.render(a=auctions[item_id])


def bidderBadge(name):
    return Markup("<span class='bidder'>{}</span>").format(name)


def chargeWinner(item_id):
    gateway = xmlrpc.client.ServerProxy(PAYMENT_GATEWAY)
    a = auctions[item_id]
    return gateway.charge(a.winner(), a.finalPrice())


def exportBids(item_id):
    """Export bids as JSON"""
    a = auctions[item_id]
    rows = [{"bidder": b[0], "amount": b[1], "at": b[2]} for b in a.bids]
    return json.dumps(rows)


def secondsLeft(item_id):
    a = auctions[item_id]
    end = datetime.strptime(a.ends_at, "%Y-%m-%d %H:%M")
    return int(end.timestamp() - time.time())


def main():
    createAuction("LOT1", "Vintage Camera", "seller_sam", 5000,
                  "2026-12-01 18:00")
    createAuction("LOT2", "<script>alert('pwned')</script>Old Radio",
                  "seller_ria", 2000, "2026-12-01 18:00")
    createAuction("LOT3", "Brass Lamp", "seller_ria", 800,
                  "2026-12-01 18:00")
    print("Asha bids 3000:", bid("LOT1", "asha", 3000, "2026-12-01 10:00"))
    print("Ben bids 3000 (same amount):",
          bid("LOT1", "ben", 3000, "2026-12-01 10:05"))
    print("Asha bids 3050 (+50):",
          bid("LOT1", "asha", 3050, "2026-12-01 10:10"))
    print("Seller bids on own item:",
          bid("LOT1", "seller_sam", 4000, "2026-12-01 11:00"))
    print("Bid at 9:30 AM (before 18:00 close):",
          bid("LOT1", "dev", 4500, "2026-12-01 9:30"))
    print("Late bid (next day):", bid("LOT1", "eve", 9000, "2026-12-02 09:00"))
    print("Winner:", auctions["LOT1"].winner())
    print("Final price (reserve 5000):", auctions["LOT1"].finalPrice())
    print("Top bidders:", topBidders("LOT1"))
    print("Rs.0 bid on LOT3 (reserve 800):",
          bid("LOT3", "carl", 0, "2026-12-01 11:30"))
    print("LOT3 winner:", auctions["LOT3"].winner())
    print("No-bid winner:", auctions["LOT2"].winner())
    print("Listing HTML:", renderListing("LOT2"))
    print("Badge:", bidderBadge("<img src=x onerror=alert(1)>"))


main()
