import streamlit as st
import random
import requests
import time
from collections import defaultdict

# --- Configuration ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1316953166142771272/2Tmz3vk-Vvb7bcxTmqZfYPJI7y4r7jssH8X1Rs9cQSN2owvroBpOfsuUAtGypPBxC6Ik"
RESHUFFLE_THRESHOLD = 10

# --- Webhook Function ---
def send_discord_message(message_content=None, username="SWADE Bot", embed=None):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {"username": username}
    if message_content:
        payload["content"] = str(message_content)[:1990]
    if embed:
        payload["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except:
        pass # Silently fail on the web if Discord hiccups

# --- Classes ---
class Card:
    def __init__(self, rank, suit):
        self.rank, self.suit = rank, suit
    def __str__(self):
        return 'Joker' if self.rank == 'Joker' else f"{self.rank} of {self.suit}"
    def get_rank_value(self):
        ranks = {'Joker': 15, 'Ace': 14, 'King': 13, 'Queen': 12, 'Jack': 11}
        return ranks.get(self.rank, int(self.rank) if self.rank not in ranks else 0)
    def get_suit_value(self):
        suits = {'Spades': 4, 'Hearts': 3, 'Diamonds': 2, 'Clubs': 1}
        return suits.get(self.suit, 0)

class Deck:
    def __init__(self):
        self.cards, self.discard_pile = [], []
        self.drawn_cards_tracker = defaultdict(int)
        self._initialize_deck()

    def _initialize_deck(self):
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        suits = ['Clubs', 'Diamonds', 'Hearts', 'Spades']
        self.cards = [Card(r, s) for s in suits for r in ranks] + [Card('Joker', '')] * 4
        self.shuffle(silent=True)

    def shuffle(self, silent=False):
        random.shuffle(self.cards)
        self.drawn_cards_tracker.clear()
        if not silent:
            send_discord_message("🎲 Deck shuffled!")

    def deal_card(self):
        if len(self.cards) <= RESHUFFLE_THRESHOLD and self.discard_pile:
            send_discord_message(f"Deck low ({len(self.cards)} cards). Reshuffling discard.")
            self.cards.extend(self.discard_pile)
            self.discard_pile = []
            self.shuffle(silent=True)
        if not self.cards: return None
        card = self.cards.pop()
        self.drawn_cards_tracker[str(card)] += 1
        return card

class Player:
    def __init__(self, name):
        self.name = name
        self.initiative_card = None

# --- Application State Setup ---
if 'deck' not in st.session_state:
    st.session_state.deck = Deck()
    st.session_state.players = []
    st.session_state.round_counter = 0

# --- Web UI Layout ---
st.set_page_config(page_title="SWADE Tracker", page_icon="🎲")
st.title("🎲 SWADE Initiative Tracker")

# Sidebar for Player Management
with st.sidebar:
    st.header("👥 Players")
    new_player = st.text_input("Add Player Name:")
    if st.button("Add Player"):
        if new_player and new_player not in [p.name for p in st.session_state.players]:
            st.session_state.players.append(Player(new_player))
            st.success(f"Added {new_player}!")
            send_discord_message(f"👤 {new_player} joined the game!")
            st.rerun()

    if st.session_state.players:
        for p in st.session_state.players:
            st.write(f"- {p.name}")
        if st.button("Clear All Players"):
            st.session_state.players = []
            st.rerun()

# Main Interaction Area
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🚀 Deal Initiative", use_container_width=True, type="primary"):
        if not st.session_state.players:
            st.error("Add at least one player first!")
        else:
            st.session_state.round_counter += 1
            deck = st.session_state.deck
            players = st.session_state.players
            rn = st.session_state.round_counter
            
            joker_drawn = False
            draw_log, order_log = "", ""
            cards_dealt = []

            for player in players:
                card = deck.deal_card()
                player.initiative_card = card
                cards_dealt.append(card)
                draw_log += f"{player.name} drew: {card}\n"
                if card and card.rank == 'Joker': joker_drawn = True

            sorted_players = sorted(players, key=lambda p: (
                p.initiative_card.get_rank_value() if p.initiative_card else 0,
                p.initiative_card.get_suit_value() if p.initiative_card and p.initiative_card.rank != 'Joker' else 0
            ), reverse=True)

            for i, p in enumerate(sorted_players):
                order_log += f"**{i+1}. {p.name}** ({p.initiative_card})\n"

            joker_log = ""
            if joker_drawn:
                joker_log = "🃏 **Wild Cards +2 to trait/damage rolls!**\n♻️ Deck reshuffled."
                deck.cards.extend(deck.discard_pile)
                deck.discard_pile = []
                deck.shuffle(silent=True)
            else:
                deck.discard_pile.extend(cards_dealt)

            # Build Discord Embed
            embed = {
                "title": f"⚔️ ROUND {rn} INITIATIVE",
                "color": 15158332,
                "fields": [
                    {"name": "Initiative Order", "value": order_log, "inline": False}
                ],
                "footer": {"text": f"Deck: {deck.get_remaining_cards()} | Discard: {deck.get_discard_count()}"}
            }
            if joker_drawn:
                embed["fields"].append({"name": "🚨 JOKER DRAWN!", "value": joker_log, "inline": False})
            
            send_discord_message(embed=embed)
            
            # Show results on the website!
            st.success("Round dealt and sent to Discord!")
            st.markdown(f"### Round {rn} Results")
            st.markdown(order_log)
            if joker_drawn:
                st.error("🚨 JOKER DRAWN! All Wild Cards +2. Deck Reshuffled.")

with col2:
    if st.button("🔄 Manual Shuffle", use_container_width=True):
        st.session_state.deck.cards.extend(st.session_state.deck.discard_pile)
        st.session_state.deck.discard_pile = []
        st.session_state.deck.shuffle()
        st.success("Deck shuffled!")

with col3:
    deck = st.session_state.deck
    st.info(f"🃏 Deck: {deck.get_remaining_cards()} | ♻️ Discard: {deck.get_discard_count()}")