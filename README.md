# 🎲 SWADE Initiative Tracker

A lightweight, interactive web application designed to manage initiative for Savage Worlds Adventure Edition (SWADE) tabletop roleplaying games. Built with Python and Streamlit, this tool allows Game Masters to effortlessly track turn order while automatically broadcasting the results directly to a Discord server via rich Embeds.

## ✨ Features

* **SWADE-Accurate Sorting:** Automatically sorts initiative draws by suit (Spades ♠️ > Hearts ♥️ > Diamonds ♦️ > Clubs ♣️) and rank.
* **Custom Deck Logic:** Uses a 54-card deck tailored for specific house rules (includes 4 Jokers instead of the standard 2).
* **Automated Joker Handling:** If a Joker is drawn, the app automatically flags the Wild Card bonus and immediately reshuffles the discard pile into the main deck for the next round.
* **Low-Deck Reshuffles:** Automatically reshuffles the discard pile back into the deck when the remaining card count drops below 10.
* **Discord Integration:** Pushes beautiful, color-coded initiative trackers and Joker alerts directly to your Discord channel so players can see the turn order in real-time.
* **Web-Based GM Screen:** A clean, button-driven UI built with Streamlit for easy player management and dealing.

## 🚀 Quick Start (Local Run)

To run this application locally on your own machine:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/lelandsgm-netizen/SWADE.git](https://github.com/lelandsgm-netizen/SWADE.git)
   cd SWADE
