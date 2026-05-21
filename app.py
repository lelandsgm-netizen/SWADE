import streamlit as st
from supabase import create_client, Client
import random
import json

# ==========================================
# 🔌 DATABASE & CORE ENGINE INITIALIZATION
# ==========================================

# Securely extract your Supabase API connections
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize standard local fallbacks for initialization protection
if "room_code" not in st.session_state:
    st.session_state.room_code = "RPGL"
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Landing Hub"
if "npc_input_name" not in st.session_state:
    st.session_state.npc_input_name = ""

# Define the complete Savage Worlds Action Deck (Including both structural Jokers)
def generate_fresh_deck():
    suits = ['♠', '♥', '♦', '♣']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{v}{s}" for v in values for s in suits]
    deck.append("🃏 Joker (Red)")
    deck.append("🃏 Joker (Black)")
    return deck

# Define the strict card value hierarchy for Savage Worlds initiative accuracy
def get_card_value(card):
    if "Joker" in card:
        return 999  # Jokers always break the top boundary to claim absolute dominance
    
    val_part = card[:-1]
    suit_part = card[-1]
    
    val_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit_map = {'♠':4, '♥':3, '♦':2, '♣':1} # Spades, Hearts, Diamonds, Clubs rule breakdown
    
    return val_map.get(val_part, 0) * 10 + suit_map.get(suit_part, 0)

# ==========================================
# 📡 CLOUD STORAGE PIPELINE FUNCTIONS (SUPABASE)
# ==========================================

def pull_room_state_from_db(room_code):
    """Fetches the complete raw row matching the active Room Code."""
    try:
        response = supabase.table("combat_sessions").select("*").eq("room_code", room_code.upper()).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        st.error(f"Cloud Read Failure: {e}")
    return None

def push_rosters_to_db(room_code, pc_list, npc_list):
    """Pushes Python rosters safely down to your new database text fields."""
    try:
        supabase.table("combat_sessions").update({
            "player_characters": json.dumps(pc_list),
            "gm_npcs": json.dumps(npc_list)
        }).eq("room_code", room_code.upper()).execute()
    except Exception as e:
        st.error(f"Cloud Roster Update Failure: {e}")

def deal_new_round_to_db(room_code, pcs, npcs):
    """Deals unique action cards to every registered combatant and advances the round."""
    current_state = pull_room_state_from_db(room_code)
    next_round = (current_state.get("round", 1) or 1) + 1 if current_state else 1
    
    deck = generate_fresh_deck()
    random.shuffle(deck)
    
    # Merge both active database tiers into a singular combat map
    full_roster = pcs + npcs
    new_hands = {}
    joker_found = False
    
    for combatant in full_roster:
        if not deck:
            deck = generate_fresh_deck()
            random.shuffle(deck)
        card = deck.pop()
        new_hands[combatant] = card
        if "Joker" in card:
            joker_found = True
            
    # Sort the deal array to display the absolute turn sequence cleanly
    sorted_deal = dict(sorted(new_hands.items(), key=lambda item: get_card_value(item[1]), reverse=True))
    
    try:
        supabase.table("combat_sessions").update({
            "sorted_hands": {"hands": sorted_deal},
            "round": next_round,
            "joker_drawn": joker_found
        }).eq("room_code", room_code.upper()).execute()
    except Exception as e:
        st.error(f"Cloud Deal Failure: {e}")

# ==========================================
# 📊 USER INTERFACE GATEWAY NAVIGATION
# ==========================================

st.sidebar.title("⚔️ Steele & Sorcery Core")
room_input = st.sidebar.text_input("Active Campaign Room Code:", value=st.session_state.room_code, max_chars=6).upper()
st.session_state.room_code = room_input

# App view modes controller
if st.sidebar.button("🛡️ Launch GM Combat Dashboard", use_container_width=True):
    st.session_state.view_mode = "GM Dashboard"
if st.sidebar.button("📱 Launch Player Table Sync", use_container_width=True):
    st.session_state.view_mode = "Player View"

# Pull data down before rendering the chosen interface view
room_data = pull_room_state_from_db(st.session_state.room_code)
active_pcs = json.loads(room_data.get("player_characters")) if room_data and room_data.get("player_characters") else []
active_npcs = json.loads(room_data.get("gm_npcs")) if room_data and room_data.get("gm_npcs") else []

# Inject color-coded layout markers for player management cards
st.markdown(
    """
    <style>
    .roster-box { padding: 12px 16px; margin-bottom: 10px; border-radius: 6px; background-color: #1a1a1e; display: flex; justify-content: space-between; align-items: center; }
    .pc-style { border-left: 5px solid #3b66a6; border-top: 1px solid #232834; border-right: 1px solid #232834; border-bottom: 1px solid #232834; }
    .npc-style { border-left: 5px solid #ff4b4b; border-top: 1px solid #232834; border-right: 1px solid #232834; border-bottom: 1px solid #232834; }
    .roster-text { color: #ffffff; font-weight: 600; font-size: 15px; }
    .badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: bold; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True
)

# ==========================================
# 🛡️ VIEW 1: THE GM COMBAT COCKPIT
# ==========================================
if st.session_state.view_mode == "GM Dashboard":
    st.title("🛡️ GM Tactical Command Centre")
    st.write(f"Secure Database Connection Active on Room Channel: **{st.session_state.room_code}**")
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("👥 Tactical Roster")
        
        # In-line text input field to register an NPC
        new_npc = st.text_input("Register New NPC/Mook Name:", value=st.session_state.npc_input_name, key="npc_entry").strip()
        if st.button("➕ Inject NPC into Grid", use_container_width=True):
            if new_npc and new_npc not in active_npcs:
                active_npcs.append(new_npc)
                push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                st.session_state.npc_input_name = "" # Reset field buffer state
                st.rerun()
                
        st.markdown("---")
        
        # Render Player Character tier with blue outline tabs
        if active_pcs:
            st.caption("🛡️ Active Wild Cards (Players)")
            for pc in active_pcs:
                col_p_text, col_p_del = st.columns([5, 1])
                with col_p_text:
                    st.markdown(f'<div class="roster-box pc-style"><span class="roster-text">{pc}</span><span class="badge" style="background-color: rgba(59,102,166,0.2); color:#7d8bff;">PLAYER</span></div>', unsafe_allow_html=True)
                with col_p_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_pc_{pc}"):
                        active_pcs.remove(pc)
                        push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                        st.rerun()

        # Render NPC tier with crimson menace markers and targeted delete trackers
        if active_npcs:
            st.caption("🚨 Threat Matrix Forces (NPCs)")
            for npc in active_npcs:
                col_n_text, col_n_del = st.columns([5, 1])
                with col_n_text:
                    st.markdown(f'<div class="roster-box npc-style"><span class="roster-text">{npc}</span><span class="badge" style="background-color: rgba(255,75,75,0.2); color:#ff4b4b;">NPC</span></div>', unsafe_allow_html=True)
                with col_n_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_npc_{npc}"):
                        active_npcs.remove(npc)
                        push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                        st.rerun()
                        
    with col_right:
        st.subheader("🎴 Live Battle Manifest Order")
        
        if st.button("🎲 Deal Action Cards & Advance Round", type="primary", use_container_width=True):
            deal_new_round_to_db(st.session_state.room_code, active_pcs, active_npcs)
            st.rerun()
            
        st.markdown("---")
        
        # Parse the structured action hands matrix down out of the nested JSON framework row
        if room_data and room_data.get("sorted_hands"):
            manifest_wrapper = room_data.get("sorted_hands", {})
            hands_map = manifest_wrapper.get("hands", {})
            current_round = room_data.get("round", 1)
            is_j_active = room_data.get("joker_drawn", False)
            
            st.markdown(f"### 📋 Current Combat Sequence: **Round {current_round}**")
            if is_j_active:
                st.error("🚨 JOKER UNLEASHED! ALL WILD CARDS GAIN +1 TO ALL TRAIT AND DAMAGE ROLLS THIS ROUND! 🚨")
                
            for idx, (name, card) in enumerate(hands_map.items()):
                card_bg = "#ff4b4b" if "Joker" in card else "#1e1e24"
                suit_color = "white" if "Joker" in card else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                
                # Check if this name exists in player array vs npc array to select the banner indicator tag
                badge_type = "PLAYER" if name in active_pcs else "NPC"
                badge_bg = "#3b66a6" if badge_type == "PLAYER" else "#ff4b4b"
                
                st.markdown(
                    f"""
                    <div style="background-color:{card_bg}; padding:14px 20px; border-radius:8px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; border:1px solid #4a4a4a;">
                        <div>
                            <span style="background-color:rgba(255,255,255,0.15); color:white; font-size:11px; padding:2px 6px; border-radius:3px; font-weight:bold; margin-right:10px;">#{idx+1}</span>
                            <strong style="font-size:16px; color:white;">{name}</strong>
                            <span style="background-color:{badge_bg}; color:white; font-size:9px; padding:2px 5px; border-radius:3px; font-weight:bold; margin-left:8px; vertical-align:middle;">{badge_type}</span>
                        </div>
                        <div style="font-size:22px; font-weight:bold; color:{suit_color};">{card}</div>
                    </div>
                    """, unsafe_allow_html=True
                )
        else:
            st.warning("No active turn tracker generated yet. Populate your tactical roster and cycle the dealer deck!")

# ==========================================
# 📱 VIEW 2: THE MOBILE-OPTIMIZED PLAYER SYNC
# ==========================================
else:
    st.header("📡 Live Table Initiative Session Sync")
    st.markdown("Enter your character parameters below to connect your device dashboard to the GM's digital console table.")
    
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        player_join_name = st.text_input("Enter Character Name:", value="", max_chars=20).strip()
    with col_p2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔗 Synch Character Connection", type="primary", use_container_width=True):
            if player_join_name and player_join_name not in active_pcs:
                active_pcs.append(player_join_name)
                push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                st.success(f"'{player_join_name}' successfully broadcast to GM Tactical Grid channel!")
                st.rerun()
                
    st.markdown("---")
    
    # Render the fluid horizontal card carousel layout blocks for players on smartphones
    if room_data and room_data.get("sorted_hands"):
        manifest_wrapper = room_data.get("sorted_hands", {})
        hands_map = manifest_wrapper.get("hands", {})
        current_round = room_data.get("round", 1)
        is_j_active = room_data.get("joker_drawn", False)
        
        st.subheader(f"🎴 Live Battle Manifest: Round {current_round}")
        if is_j_active:
            st.error("🚨 A JOKER HAS BEEN UNLEASHED! INITIATIVE ADVANTAGE ENGAGED. 🚨")
            
        st.markdown(
            """
            <style>
            .mobile-card-container { display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 12px; padding: 10px 4px; -webkit-overflow-scrolling: touch; }
            .mobile-initiative-card { flex: 0 0 140px; text-align: center; padding: 14px; border-radius: 6px; border: 1px solid #4a4a4a; min-height: 120px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .mobile-card-container::-webkit-scrollbar { display: none; }
            </style>
            """, unsafe_allow_html=True
        )
        
        html_carousel = '<div class="mobile-card-container">'
        
        for idx, (name, card) in enumerate(hands_map.items()):
            badge_lbl = "PLAYER" if name in active_pcs else "NPC"
            badge_color = "#3b66a6" if badge_lbl == "PLAYER" else "#ff4b4b"
            
            is_joker_card = "Joker" in card
            bg_card_hex = "#ff4b4b" if is_joker_card else "#1e1e24"
            suit_text_hex = "white" if is_joker_card else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
            
            html_carousel += f"""
            <div class="mobile-initiative-card" style="background-color: {bg_card_hex};">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:4px; margin-bottom:8px;">
                    <strong style="font-size:11px; color:white; text-transform:uppercase; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80px;">{name}</strong>
                    <span style="background-color:{badge_color}; color:white; font-size:8px; padding:1px 3px; border-radius:2px; font-weight:bold;">#{idx+1}</span>
                </div>
                <div style="font-size:26px; font-weight:bold; color:{suit_text_hex}; margin-top:8px;">{card}</div>
            </div>
            """
            
        html_carousel += '</div>'
        st.markdown(html_carousel, unsafe_allow_html=True)
        st.info("📱 Swipe horizontally across the cards to view the complete operational combat order flow.")
    else:
        st.warning("Waiting for the Game Master to deal action cards for this room session...")
