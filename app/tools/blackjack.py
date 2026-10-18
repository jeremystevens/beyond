"""Blackjack rules, ported unchanged from PromptetheusBot (offline, no betting).

One 52-card deck shuffled per hand with the OS's secure random source; the dealer shows one card (the hole card stays
hidden until you stand or bust), draws to 17 and stands on all 17s; naturals are checked right after the deal; you
stand automatically on 21.
"""
import secrets

RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
SUITS = ['♠', '♥', '♦', '♣']
OUTCOMES = {   # result -> (message, outcome for the shared game stats, column in blackjack_stats)
    'blackjack': ('Blackjack! You win!', 'win', 'wins'),
    'win': ('You win!', 'win', 'wins'),
    'dealer_bust': ('Dealer busts. You win!', 'win', 'wins'),
    'lose': ('Dealer wins.', 'loss', 'losses'),
    'bust': ('Bust! Dealer wins.', 'loss', 'losses'),
    'dealer_blackjack': ('Dealer has blackjack. Dealer wins.', 'loss', 'losses'),
    'push': ("Push: it's a tie.", 'draw', 'pushes'),
}
DEAL_NOTES = {   # a natural on the deal ends the hand before you can act; say why
    'dealer_blackjack': ('The dealer was dealt an ace and a 10-value card (a natural 21), so the hand ends right '
                         'away: nothing you could do would beat it. That happens about once every 21 hands.'),
    'blackjack': 'You were dealt an ace and a 10-value card: an instant win, no need to hit or stand!',
    'push': 'You and the dealer were both dealt blackjack, so the hand is a tie.',
}
RULES = ('Blackjack rules\n'
         '• Get closer to 21 than the dealer without going over.\n'
         '• Number cards count their value, J/Q/K count 10, A counts 1 or 11.\n'
         "• You only see the dealer's first card until you stand.\n"
         '• Hit = take a card · Stand = keep your hand. You stand automatically on 21.\n'
         '• The dealer draws until 17 or more.\n'
         '• An ace and a 10-value card on the deal is blackjack.\n'
         'Commands: /blackjack · /blackjack stats · /blackjack rules (/bj works too)')


def deck():
    cards = [rank + suit for suit in SUITS for rank in RANKS]
    secrets.SystemRandom().shuffle(cards)
    return cards


def hand_value(cards):
    """(best total, is_soft)."""
    total, aces = 0, 0
    for card in cards:
        rank = card[:-1]
        total += 11 if rank == 'A' else 10 if rank in ('J', 'Q', 'K', '10') else int(rank)
        aces += rank == 'A'
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0 and total <= 21


def is_blackjack(cards):
    return len(cards) == 2 and hand_value(cards)[0] == 21


def deal(cards=None):
    """A new hand: {'deck', 'player', 'dealer', 'result', 'natural'}; a natural ends it on the deal."""
    cards = list(cards) if cards is not None else deck()
    hand = {'deck': cards, 'player': [cards.pop(), cards.pop()], 'dealer': [cards.pop(), cards.pop()],
            'result': None, 'natural': False}
    player_bj, dealer_bj = is_blackjack(hand['player']), is_blackjack(hand['dealer'])
    if player_bj or dealer_bj:
        hand['result'] = 'push' if player_bj and dealer_bj else 'blackjack' if player_bj else 'dealer_blackjack'
        hand['natural'] = True
    return hand


def finish(hand):
    """The dealer plays out the hand; sets hand['result']."""
    player_total = hand_value(hand['player'])[0]
    if player_total > 21:
        hand['result'] = 'bust'
        return hand
    while hand_value(hand['dealer'])[0] < 17:
        hand['dealer'].append(hand['deck'].pop())
    dealer_total = hand_value(hand['dealer'])[0]
    hand['result'] = ('dealer_bust' if dealer_total > 21 else 'win' if player_total > dealer_total
                      else 'lose' if player_total < dealer_total else 'push')
    return hand


def hit(hand):
    """Draw a card; on 21 or a bust the hand finishes by itself."""
    hand['player'].append(hand['deck'].pop())
    if hand_value(hand['player'])[0] >= 21:
        finish(hand)
    return hand
