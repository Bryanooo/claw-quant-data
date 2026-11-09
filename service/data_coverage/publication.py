"""Publication windows shared by coverage audits and repair scheduling."""

# A same-day empty response from these feeds is provisional. A fresh request
# on a later Shanghai business date can certify a genuinely empty slice.
NEXT_DAY_EMPTY_CONFIRMATION = frozenset({
    "dc_hot", "ths_hot", "ggt_daily", "hk_hold", "forex_daily",
    "kpl_list", "stk_auction_o", "stk_auction_c",
})
