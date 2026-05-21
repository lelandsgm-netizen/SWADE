import streamlit as st
from supabase import create_client, Client
import random
import json
import re

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
if "dice_log" not in st.session_state:
    st.session_state.dice_log = []

# Define the complete Savage Worlds Action Deck
def generate_fresh_deck():
    suits = ['♠', '♥', '♦', '♣']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{v}{s}" for v in values for s in suits]
    deck.append("🃏 Joker (Red)")
    deck.append("🃏 Joker (Black)")
    return deck

# Strict card value hierarchy for SWADE initiative accuracy
def get_card_value(card):
    if "Joker" in card:
        return 999  
    val_part = card[:-1]
    suit_part = card[-1]
    val_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit_map = {'♠':4, '♥':3, '♦':2, '♣':1}
    return val_map.get(val_part, 0) * 10 + suit_map.get(suit_part, 0)

# ==========================================
# 🎲 SAVAGE WORLDS EXPLODING DICE LOGIC
# ==========================================

def roll_savage_die(sides, is_wild=False):
    """Rolls a single die with infinite SWADE explosions if maximum value is hit."""
    if sides < 2: 
        return [0], 0
    
    rolls = []
    while True:
        roll = random.randint(1, sides)
        rolls.append(roll)
        if roll != sides:
            break
    return rolls, sum(rolls)

def execute_swade_roll(trait_str, wild_str="d6", modifier=0):
    """Executes a trait die vs wild die roll with accurate mathematical parsing."""
    try:
        t_sides = int(re.findall(r'\d+', trait_str)[0])
        w_sides = int(re.findall(r'\d+', wild_str)[0]) if wild_str else 0
    except:
        return "Format Error! Use formats like 'd8'."
        
    t_rolls, t_total = roll_savage_die(t_sides)
    
    if w_sides > 0:
        w_rolls, w_total = roll_savage_die(w_sides, is_wild=True)
        # Apply static modifier to the highest base engine result
        highest_base = max(t_total, w_total)
        final_total = highest_base + modifier
        
        result_msg = (
            f"🎲 **Trait {trait_str}** (Rolled {t_rolls} = {t_total}) | "
            f"**Wild {wild_str}** (Rolled {w_rolls} = {w_total})\n\n"
            f"🔥 **Highest Base:** {highest_base} + Mod ({modifier}) = **{final_total}**"
        )
    else:
        final_total = t_total + modifier
        result_msg = f"🎲 **Damage Roll {trait_str}:** Rolled {t_rolls} + Mod ({modifier}) = **{final_total}**"
        
    return result_msg

# ==========================================
# 📡 CLOUD STORAGE PIPELINE FUNCTIONS (SUPABASE)
# ==========================================

def pull_room_state_from_db(room_code):
    try:
        response = supabase.table("combat_sessions").select("*").eq("room_code", room_code.upper()).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        st.error(f"Cloud Read Failure: {e}")
    return None

def push_rosters_to_db(room_code, pc_list, npc_list):
    try:
        supabase.table("combat_sessions").update({
            "player_characters": json.dumps(pc_list),
            "gm_npcs": json.dumps(npc_list)
        }).eq("room_code", room_code.upper()).execute()
    except Exception as e:
        st.error(f"Cloud Roster Update Failure: {e}")

def deal_new_round_to_db(room_code, pcs, npcs):
    current_state = pull_room_state_from_db(room_code)
    next_round = (current_state.get("round", 1) or 1) + 1 if current_state else 1
    
    deck = generate_fresh_deck()
    random.shuffle(deck)
    
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
# 📊 USER INTERFACE & NAVIGATION SIDEBAR
# ==========================================

st.sidebar.title("⚔️ Steele & Sorcery Core")
room_input = st.sidebar.text_input("Active Campaign Room Code:", value=st.session_state.room_code, max_chars=6).upper()
st.session_state.room_code = room_input

if st.sidebar.button("🛡️ Launch GM Combat Dashboard", use_container_width=True):
    st.session_state.view_mode = "GM Dashboard"
if st.sidebar.button("📱 Launch Player Table Sync", use_container_width=True):
    st.session_state.view_mode = "Player View"

# Pull down active table rows from Supabase
room_data = pull_room_state_from_db(st.session_state.room_code)
active_pcs = json.loads(room_data.get("player_characters")) if room_data and room_data.get("player_characters") else []
active_npcs = json.loads(room_data.get("gm_npcs")) if room_data and room_data.get("gm_npcs") else []

# Custom colored border styling rules
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
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("👥 Tactical Roster")
        
        new_npc = st.text_input("Register New NPC/Mook Name:", value=st.session_state.npc_input_name, key="npc_entry").strip()
        if st.button("➕ Inject NPC into Grid", use_container_width=True):
            if new_npc and new_npc not in active_npcs:
                active_npcs.append(new_npc)
                push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                st.session_state.npc_input_name = ""
                st.rerun()
                
        st.markdown("---")
        
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
        
        if room_data and room_data.get("sorted_hands"):
            manifest_wrapper = room_data.get("sorted_hands", {})
            hands_map = manifest_wrapper.get("hands", {})
            current_round = room_data.get("round", 1)
            is_j_active = room_data.get("joker_drawn", False)
            
            st.markdown(f"### 📋 Current Combat Sequence: **Round {current_round}**")
            if is_j_active:
                st.error("🚨 JOKER UNLEASHED! ALL WILD CARDS GAIN +1 TO ALL TRAIT AND DAMAGE ROLLS! 🚨")
                
            for idx, (name, card) in enumerate(hands_map.items()):
                card_bg = "#ff4b4b" if "Joker" in card else "#1e1e24"
                suit_color = "white" if "Joker" in card else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                badge_type = "PLAYER" if name in active_pcs else "NPC"
                badge_bg = "#3b66a6" if badge_type == "PLAYER" else "#ff4b4b"
