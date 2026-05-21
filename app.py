import streamlit as st
from supabase import create_client, Client
import random
import json
import re

# ==========================================
# 🔌 DATABASE & CORE ENGINE INITIALIZATION
# ==========================================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🌟 CRITICAL FIX: Session-Lock tracking to force a clean slate on browser open
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = True
    st.session_state.room_code = "RPGL"
    st.session_state.view_mode = "GM Dashboard"
    st.session_state.npc_input_name = ""
    st.session_state.dice_log = []
    
    # Force wipe the database row for this room immediately on fresh browser launch
    try:
        supabase.table("combat_sessions").update({
            "player_characters": json.dumps([]),
            "gm_npcs": json.dumps([]),
            "sorted_hands": {"hands": {}},
            "round": 1,
            "joker_drawn": False
        }).eq("room_code", "RPGL").execute()
    except:
        pass

def generate_fresh_deck():
    suits = ['♠', '♥', '♦', '♣']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{v}{s}" for v in values for s in suits]
    deck.append("🃏 Joker (Red)")
    deck.append("🃏 Joker (Black)")
    return deck

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

def roll_savage_die(sides):
    if sides < 2: return [0], 0
    rolls = []
    while True:
        roll = random.randint(1, sides)
        rolls.append(roll)
        if roll != sides: break
    return rolls, sum(rolls)

def execute_swade_roll(trait_str, wild_str="d6", modifier=0):
    try:
        t_sides = int(re.findall(r'\d+', trait_str)[0])
        w_sides = int(re.findall(r'\d+', wild_str)[0]) if wild_str else 0
    except:
        return "Format Error!"
        
    t_rolls, t_total = roll_savage_die(t_sides)
    
    if w_sides > 0:
        w_rolls, w_total = roll_savage_die(w_sides)
        highest_base = max(t_total, w_total)
        final_total = highest_base + modifier
        result_msg = f"🎲 **{trait_str} vs {wild_str}**: {t_rolls} | Wild: {w_rolls} + Mod ({modifier}) = **{final_total}**"
    else:
        final_total = t_total + modifier
        result_msg = f"💥 **Damage {trait_str}**: {t_rolls} + Mod ({modifier}) = **{final_total}**"
        
    return result_msg

# ==========================================
# 📡 CLOUD STORAGE PIPELINE FUNCTIONS
# ==========================================

def pull_room_state_from_db(room_code):
    try:
        response = supabase.table("combat_sessions").select("*").eq("room_code", room_code.upper()).execute()
        if response.data: return response.data[0]
    except:
        pass
    return None

def push_rosters_to_db(room_code, pc_list, npc_list):
    try:
        supabase.table("combat_sessions").update({
            "player_characters": json.dumps(pc_list),
            "gm_npcs": json.dumps(npc_list)
        }).eq("room_code", room_code.upper()).execute()
    except Exception as e:
        st.error(f"Roster Sync Failed: {e}")

def deal_new_round_to_db(room_code, pcs, npcs):
    current_state = pull_room_state_from_db(room_code)
    next_round = (current_state.get("round", 0) or 0) + 1 if current_state else 1
    
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
        if "Joker" in card: joker_found = True
            
    sorted_deal = dict(sorted(new_hands.items(), key=lambda item: get_card_value(item[1]), reverse=True))
    
    try:
        supabase.table("combat_sessions").update({
            "sorted_hands": {"hands": sorted_deal},
            "round": next_round,
            "joker_drawn": joker_found
        }).eq("room_code", room_code.upper()).execute()
    except Exception as e:
        st.error(f"Deal Sync Failed: {e}")

# ==========================================
# 📊 USER INTERFACE & NAVIGATION SIDEBAR
# ==========================================

st.sidebar.title("⚔️ Steele & Sorcery Core")
room_input = st.sidebar.text_input("Active Room Code:", value=st.session_state.room_code, max_chars=6).upper()
st.session_state.room_code = room_input

if st.sidebar.button("🛡️ Launch GM Dashboard", use_container_width=True):
    st.session_state.view_mode = "GM Dashboard"
    st.rerun()
if st.sidebar.button("📱 Launch Player Table Sync", use_container_width=True):
    st.session_state.view_mode = "Player View"
    st.rerun()

# Read live parameters straight from DB text fields
room_data = pull_room_state_from_db(st.session_state.room_code)
active_pcs = json.loads(room_data.get("player_characters")) if room_data and room_data.get("player_characters") else []
active_npcs = json.loads(room_data.get("gm_npcs")) if room_data and room_data.get("gm_npcs") else []

# Custom CSS Styles Injection
st.markdown(
    """
    <style>
    .roster-box { padding: 12px 16px; margin-bottom: 8px; border-radius: 6px; background-color: #1c212b; display: flex; justify-content: space-between; align-items: center; border: 1px solid #2d3545; }
    .pc-style { border-left: 5px solid #3b66a6; }
    .npc-style { border-left: 5px solid #ff4b4b; }
    .roster-text { color: #ffffff; font-weight: 600; font-size: 15px; }
    .badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True
)

# ==========================================
# 🛡️ VIEW 1: THE GM COMBAT DASHBOARD
# ==========================================
if st.session_state.view_mode == "GM Dashboard":
    st.title("🛡️ GM Tactical Command Centre")
    st.caption(f"Connected to Room Code: **{st.session_state.room_code}**")
    
    # --------------------------------------
    # 🎴 SECTION 1: MASTER INITIATIVE TRACKER
    # --------------------------------------
    st.markdown("## 🎴 Live Battle Manifest Order")
    
    if st.button("🎲 Deal Cards & Advance Round", type="primary", use_container_width=True):
        deal_new_round_to_db(st.session_state.room_code, active_pcs, active_npcs)
        st.rerun()
        
    if room_data and room_data.get("sorted_hands"):
        manifest_wrapper = room_data.get("sorted_hands", {})
        hands_map = manifest_wrapper.get("hands", {})
        current_round = room_data.get("round", 1)
        
        st.markdown(f"### 📋 Current Turn Order: **Round {current_round}**")
        if room_data.get("joker_drawn", False):
            st.error("🚨 JOKER UNLEASHED! +1 to Trait and Damage rolls for those holding the Wild Card! 🚨")
            
        for idx, (name, card) in enumerate(hands_map.items()):
            card_bg = "#ff4b4b" if "Joker" in card else "#1c212b"
            suit_color = "white" if "Joker" in card else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
            b_lbl = "PLAYER" if name in active_pcs else "NPC"
            b_bg = "#3b66a6" if b_lbl == "PLAYER" else "#ff4b4b"
            
            st.markdown(
                f"""
                <div style="background-color:{card_bg}; padding:14px; border-radius:8px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; border:1px solid #2d3545;">
                    <div>
                        <span style="background-color:rgba(255,255,255,0.15); color:white; font-size:11px; padding:2px 6px; border-radius:3px; font-weight:bold; margin-right:10px;">#{idx+1}</span>
                        <strong style="font-size:16px; color:white;">{name}</strong>
                        <span style="background-color:{b_bg}; color:white; font-size:9px; padding:2px 5px; border-radius:3px; font-weight:bold; margin-left:8px;">{b_lbl}</span>
                    </div>
                    <div style="font-size:20px; font-weight:bold; color:{suit_color};">{card}</div>
                </div>
                """, unsafe_allow_html=True
            )
    else:
        st.warning("No active cards are out on the field. Populate the roster below and deal a round!")
        
    st.markdown("---")
    
    # --------------------------------------
    # 👥 SECTION 2: ROSTER CREATION SHIELD
    # --------------------------------------
    st.markdown("## 👥 Tactical Combat Roster")
    
    new_npc = st.text_input("Enter NPC / Threat Name:", value=st.session_state.npc_input_name, key="npc_entry").strip()
    if st.button("➕ Add Threat to Room", use_container_width=True):
        if new_npc and new_npc not in active_npcs:
            active_npcs.append(new_npc)
            push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
            st.session_state.npc_input_name = ""
            st.rerun()
            
    # Display Player Characters
    if active_pcs:
        st.caption("🛡️ Active Player Characters")
        for pc in active_pcs:
            c_txt, c_del = st.columns([6, 1])
            with c_txt:
                st.markdown(f'<div class="roster-box pc-style"><span class="roster-text">{pc}</span><span class="badge" style="background-color:rgba(59,102,166,0.2); color:#7d8bff;">PLAYER</span></div>', unsafe_allow_html=True)
            with c_del:
                if st.button("🗑️", key=f"del_pc_{pc}", use_container_width=True):
                    active_pcs.remove(pc)
                    push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                    st.rerun()

    # Display NPCs
    if active_npcs:
        st.caption("🚨 Active Threat Targets")
        for npc in active_npcs:
            c_txt, c_del = st.columns([6, 1])
            with c_txt:
                st.markdown(f'<div class="roster-box npc-style"><span class="roster-text">{npc}</span><span class="badge" style="background-color:rgba(255,75,75,0.2); color:#ff4b4b;">NPC</span></div>', unsafe_allow_html=True)
            with c_del:
                if st.button("🗑️", key=f"del_npc_{npc}", use_container_width=True):
                    active_npcs.remove(npc)
                    push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                    st.rerun()

    st.markdown("---")

    # --------------------------------------
    # 🎲 SECTION 3: GM SCREEN DICE TRAY
    # --------------------------------------
    st.markdown("## 🎲 GM Operational Dice Shield")
    
    gm_trait = st.selectbox("Select Trait Die:", ["d4", "d6", "d8", "d10", "d12"], index=1, key="gm_t")
    gm_wild = st.selectbox("Select Wild Die:", ["d6", "None (Standard Extra)"], index=0, key="gm_w")
    gm_w_pass = None if "None" in gm_wild else "d6"
    gm_mod = st.number_input("Global Modifier:", value=0, step=1, key="gm_m")
    
    if st.button("🎲 Roll Action Check", use_container_width=True, key="gm_roll"):
        res = execute_swade_roll(gm_trait, gm_w_pass, gm_mod)
        st.session_state.dice_log.insert(0, res)
        
    st.caption("微 Fast Quick-Strike Attack Tracks")
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        if st.button("🧟 Zombie Scratch (d6 No Wild)", use_container_width=True):
            st.session_state.dice_log.insert(0, "🧟 **Mook Strike:** " + execute_swade_roll("d6", None, 0))
    with c_m2:
        if st.button("😈 Boss Strike (d8 vs d6)", use_container_width=True):
            st.session_state.dice_log.insert(0, "😈 **Wild Card Threat:** " + execute_swade_roll("d8", "d6", 0))
            
    if st.session_state.dice_log:
        st.markdown("### 📜 Session Action Output Log")
        if st.button("🗑️ Clear Log Console", use_container_width=True):
            st.session_state.dice_log = []
            st.rerun()
        for log in st.session_state.dice_log:
            st.info(log)

# ==========================================
# 📱 VIEW 2: THE MOBILE PLAYER WORKSPACE
# ==========================================
else:
    st.title("📱 Player Synch Dashboard")
    tab_init, tab_dice = st.tabs(["📡 Live Turn Order", "🎲 Dice Tray & Quick Macros"])
    
    with tab_init:
        st.markdown("### Connect Your Character to the Grid")
        p_name = st.text_input("Character Name:", value="", max_chars=20, key="p_join").strip()
        if st.button("🔗 Synch Connection to Table", type="primary", use_container_width=True):
            if p_name and p_name not in active_pcs:
                active_pcs.append(p_name)
                push_rosters_to_db(st.session_state.room_code, active_pcs, active_npcs)
                st.success(f"Connected '{p_name}' successfully!")
                st.rerun()
                
        st.markdown("---")
        
        if room_data and room_data.get("sorted_hands"):
            manifest_wrapper = room_data.get("sorted_hands", {})
            hands_map = manifest_wrapper.get("hands", {})
            current_round = room_data.get("round", 1)
            
            st.subheader(f"🎴 Turn Sequence Manifest: Round {current_round}")
            
            st.markdown(
                """
                <style>
                .mobile-card-container { display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 12px; padding: 10px 4px; -webkit-overflow-scrolling: touch; }
                .mobile-initiative-card { flex: 0 0 130px; text-align: center; padding: 12px; border-radius: 6px; border: 1px solid #2d3545; min-height: 110px; background-color:#1c212b; }
                .mobile-card-container::-webkit-scrollbar { display: none; }
                </style>
                """, unsafe_allow_html=True
            )
            
            html_carousel = '<div class="mobile-card-container">'
            for idx, (name, card) in enumerate(hands_map.items()):
                badge_lbl = "PLAYER" if name in active_pcs else "NPC"
                badge_color = "#3b66a6" if badge_lbl == "PLAYER" else "#ff4b4b"
                is_joker = "Joker" in card
                bg_hex = "#ff4b4b" if is_joker else "#1c212b"
                s_hex = "white" if is_joker else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                
                html_carousel += f"""
                <div class="mobile-initiative-card" style="background-color: {bg_hex};">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px; margin-bottom:6px;">
                        <strong style="font-size:11px; color:white; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70px;">{name}</strong>
                        <span style="background-color:{badge_color}; color:white; font-size:8px; padding:1px 3px; border-radius:2px; font-weight:bold;">#{idx+1}</span>
                    </div>
                    <div style="font-size:24px; font-weight:bold; color:{s_hex}; margin-top:4px;">{card}</div>
                </div>
                """
            html_carousel += '</div>'
            st.markdown(html_carousel, unsafe_allow_html=True)
            st.info("📱 Swipe across the row cards to scroll the full turn order sequence.")
        else:
            st.warning("Waiting for the GM to deal cards for this session...")

    with tab_dice:
        st.subheader("🎲 Action Dice Tray")
        p_trait = st.selectbox("Trait Die:", ["d4", "d6", "d8", "d10", "d12"], index=1, key="p_t")
        p_wild = st.selectbox("Wild Die:", ["d6", "None"], index=0, key="p_w")
        p_w_pass = None if p_wild == "None" else "d6"
        p_mod = st.number_input("Modifier:", value=0, step=1, key="p_m")
        
        if st.button("🔥 Roll Trait Check", type="primary", use_container_width=True):
            st.session_state.dice_log.insert(0, execute_swade_roll(p_trait, p_w_pass, p_mod))
            st.rerun()
            
        st.markdown("---")
        st.subheader("⚔️ Attack Macros")
        if st.button("🗡️ Fighting Slash (d8 vs d6)", use_container_width=True):
            st.session_state.dice_log.insert(0, "⚔️ **Fighting:** " + execute_swade_roll("d8", "d6", 0))
            st.rerun()
        if st.button("🏹 Shooting Launch (d6 vs d6 + 1)", use_container_width=True):
            st.session_state.dice_log.insert(0, "🎯 **Shooting:** " + execute_swade_roll("d6", "d6", 1))
            st.rerun()
            
        if st.session_state.dice_log:
            st.markdown("### 📜 Personal Action History Log")
            if st.button("🗑️ Reset Log Windows", use_container_width=True):
                st.session_state.dice_log = []
                st.rerun()
            for log in st.session_state.dice_log:
                st.info(log)
