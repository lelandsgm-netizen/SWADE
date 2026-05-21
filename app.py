import streamlit as st
import random
import requests
import re
import json
from supabase import create_client, Client
from streamlit_local_storage import LocalStorage

# --- Global Page Configuration ---
st.set_page_config(page_title="SWADE Master Toolkit", page_icon="🃏", layout="wide")

local_storage = LocalStorage()

# --- Secure Server Environment Variables Integration ---
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", None)
SUPABASE_URL = st.secrets.get("SUPABASE_URL", None)
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", None)

# Initialize Supabase Engine if secrets exist safely
supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        pass

# --- Persistent Session State Configuration ---
if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = True
    st.session_state.deck = []
    st.session_state.discard = []
    st.session_state.joker_drawn = False
    st.session_state.roll_history = []
    st.session_state.round_counter = 0
    st.session_state.round_history = [] 
    st.session_state.current_round_hands = {}
    st.session_state.connected_room_code = "SWAD"
    # Added state trackers for the manual override loading system
    st.session_state.manual_mode = "📊 Trait Test"
    st.session_state.d_str_input = "1d10+1d6"
    st.session_state.d_ap_input = 0

# ==========================================
#     🌟 DATABASE CLOUD SYNC OPERATIONS
# ==========================================
def push_initiative_to_db(room_code, sorted_hands_dict, round_num):
    """Pushes a live round card manifest to the Supabase cloud table."""
    if not supabase_client: return
    
    payload = {"round": round_num, "joker_drawn": st.session_state.joker_drawn, "hands": sorted_hands_dict}
    try:
        response = supabase_client.table("combat_sessions").select("*").eq("room_code", room_code.upper()).execute()
        if response.data:
            supabase_client.table("combat_sessions").update({"sorted_hands": payload}).eq("room_code", room_code.upper()).execute()
        else:
            supabase_client.table("combat_sessions").insert({"room_code": room_code.upper(), "sorted_hands": payload}).execute()
    except:
        pass

def pull_initiative_from_db(room_code):
    """Retrieves the live synchronized round manifest from the cloud."""
    if not supabase_client: return None
    try:
        response = supabase_client.table("combat_sessions").select("sorted_hands").eq("room_code", room_code.upper()).execute()
        if response.data and response.data[0].get("sorted_hands"):
            return response.data[0]["sorted_hands"]
    except:
        pass
    return None

def pull_room_state(room_code):
    """Retrieves the complete state including the new text array columns."""
    if not supabase_client: return None
    try:
        response = supabase_client.table("combat_sessions").select("*").eq("room_code", room_code.upper()).execute()
        if response.data: return response.data[0]
    except:
        pass
    return None

def push_rosters_to_db(room_code, pcs, npcs):
    """Writes the active character arrays back to the Supabase text columns."""
    if not supabase_client: return
    try:
        supabase_client.table("combat_sessions").update({
            "player_characters": json.dumps(pcs),
            "gm_npcs": json.dumps(npcs)
        }).eq("room_code", room_code.upper()).execute()
    except:
        pass

# ==========================================
#      CARD DEALER ENGINE CORES
# ==========================================
def build_deck():
    suits = ['♠', '♥', '♦', '♣']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{v}{s}" for v in values for s in suits]
    deck.append("🃏 Red Joker")
    deck.append("🃏 Black Joker")
    return deck

def shuffle_deck():
    st.session_state.deck = build_deck()
    random.shuffle(st.session_state.deck)
    st.session_state.discard = []
    st.session_state.joker_drawn = False

if not st.session_state.deck and not st.session_state.discard:
    shuffle_deck()

def get_card_weight(card_str):
    if "Joker" in card_str: return 9999
    val_part = card_str[:-1]
    suit_part = card_str[-1]
    value_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit_map = {'♠':4, '♥':3, '♦':2, '♣':1}
    return (value_map.get(val_part, 0) * 100) + suit_map.get(suit_part, 0)

def deal_to_roster(roster_list):
    hands = {}
    for actor in roster_list:
        if not st.session_state.deck:
            shuffle_deck()
        card = st.session_state.deck.pop(0)
        hands[actor] = card
        if "Joker" in card:
            st.session_state.joker_drawn = True
            
    sorted_hands = dict(sorted(hands.items(), key=lambda item: get_card_weight(item[1]), reverse=True))
    
    st.session_state.round_counter += 1
    st.session_state.current_round_hands = sorted_hands
    st.session_state.round_history.insert(0, (st.session_state.round_counter, list(sorted_hands.items())))
    st.session_state.discard.extend(sorted_hands.values())
    
    # CLOUD SYNC EXECUTION
    push_initiative_to_db(st.session_state.connected_room_code, sorted_hands, st.session_state.round_counter)
    send_initiative_to_discord(sorted_hands, st.session_state.round_counter)

def send_initiative_to_discord(sorted_hands, round_num):
    if not DISCORD_WEBHOOK_URL: return
    fields = []
    for idx, (actor_name, card_value) in enumerate(sorted_hands.items(), 1):
        status = "ACTING FIRST" if idx == 1 else f"Turn Order #{idx}"
        if "Joker" in card_value: status = "🃏 JOKER (Actions +2 / Toughness +2)"
        fields.append({"name": f"{idx}. {actor_name.upper()}", "value": f"Card: **{card_value}**\n*{status}*", "inline": False})
        
    embed = {"title": f"⚔️ Initiative Dispatched: Round {round_num}", "color": 3447003, "fields": fields}
    payload = {"username": "SWADE Turn Bot", "embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except:
        pass

# ==========================================
#      DICE ROLLER MATH CORE ENGINES
# ==========================================
def roll_single_die(sides):
    rolls = []
    while True:
        roll = random.randint(1, sides)
        rolls.append(roll)
        if roll == sides: continue
        break
    return rolls

def parse_dice_string(dice_string):
    cleaned = dice_string.lower().replace(" ", "")
    dice_matches = re.findall(r'([+-]?\d*)d(\d+)', cleaned)
    remainder = re.sub(r'([+-]?\d*)d(\d+)', '', cleaned)
    modifier = 0
    if remainder:
        mod_matches = re.findall(r'([+-]?\d+)', remainder)
        for mod in mod_matches: modifier += int(mod)
    dice_to_roll = []
    for count_str, sides_str in dice_matches:
        count = 1
        if count_str and count_str != '+' and count_str != '-':
            count = int(count_str)
        elif count_str == '-':
            count = -1
        sides = int(sides_str)
        dice_to_roll.append((count, sides))
    return dice_to_roll, modifier

def calculate_resolution(total, tn):
    net = total - tn
    if net < 0:
        return "Failure", 9807243
    else:
        raises = net // 4
        return ("🎯 Success!" if raises == 0 else f"🔥 Success with {raises} Raise(s)!"), (3066993 if raises == 0 else 15105570)

def execute_dropdown_trait_roll(player_name, die_sides, situational_mod, map_penalty, target_number, is_frenzy=False):
    fields_log = []
    total_modifier = situational_mod + map_penalty
    mod_sign = f"+{total_modifier}" if total_modifier >= 0 else f"{total_modifier}"
    wild_rolls = roll_single_die(6)
    wild_total = sum(wild_rolls)
    wild_trail = " -> ".join([f"[{r}]" if r != 6 else f"[{r}]💥" for r in wild_rolls])
    
    if not is_frenzy:
        trait_rolls = roll_single_die(die_sides)
        trait_total = sum(trait_rolls)
        trait_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in trait_rolls])
        fields_log.append({"name": f"🎲 Trait Die (d{die_sides})", "value": f"{trait_trail} = **{trait_total}**", "inline": True})
        fields_log.append({"name": "🃏 Wild Die (d6)", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        if trait_rolls[0] == 1 and wild_rolls[0] == 1:
            res_text, color = "💀 CRITICAL FAILURE! 💀", 15158332
            base_die, final_total = 0, 0
        else:
            base_die = max(trait_total, wild_total)
            final_total = base_die + total_modifier
            res_text, color = calculate_resolution(final_total, target_number)
        breakdown_text = f"Highest Die ({base_die})" + (f" + Sit Mod ({situational_mod})" if situational_mod != 0 else "") + (f" + MAP Penalty ({map_penalty})" if map_penalty != 0 else "") + f" = **{final_total}**"
        fields_log.append({"name": "📈 Math Breakdown", "value": breakdown_text, "inline": False})
        fields_log.append({"name": "📢 Resolution", "value": f"**{res_text}** (vs TN {target_number})", "inline": False})
        title_text = f"📊 Trait Test: d{die_sides} (Net Mod: {mod_sign})"
    else:
        t1_rolls, t2_rolls = roll_single_die(die_sides), roll_single_die(die_sides)
        t1_total, t2_total = sum(t1_rolls), sum(t2_rolls)
        t1_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t1_rolls])
        t2_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t2_rolls])
        fields_log.append({"name": "⚔️ Attack Die #1", "value": f"{t1_trail} = **{t1_total}**", "inline": True})
        fields_log.append({"name": "⚔️ Attack Die #2", "value": f"{t2_trail} = **{t2_total}**", "inline": True})
        fields_log.append({"name": "🃏 Shared Wild Die", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        if t1_rolls[0] == 1 and t2_rolls[0] == 1 and wild_rolls[0] == 1:
            fields_log.append({"name": "🚨 COMBAT DISASTER", "value": "💀 **CRITICAL FAILURE ON BOTH ATTACKS!** 💀", "inline": False})
            color = 15158332
        else:
            best_combo = max([[t1_total, t2_total], [wild_total, t2_total], [t1_total, wild_total]], key=lambda x: (sum(x), max(x)))
            f1, f2 = best_combo[0] + total_modifier, best_combo[1] + total_modifier
            res1, _ = calculate_resolution(f1, target_number)
            res2, _ = calculate_resolution(f2, target_number)
            pen = (f" + Sit Mod ({situational_mod})" if situational_mod != 0 else "") + (f" + MAP Penalty ({map_penalty})" if map_penalty != 0 else "")
            fields_log.append({"name": "⚔️ Attack #1 Outcome", "value": f"Base ({best_combo[0]}){pen} = **{f1}**\n↳ **{res1}**", "inline": False})
            fields_log.append({"name": "⚔️ Attack #2 Outcome", "value": f"Base ({best_combo[1]}){pen} = **{f2}**\n↳ **{res2}**", "inline": False})
            color = 15105570
        title_text = f"⚔️ Frenzy Full Attack: 2x d{die_sides} (Net Mod: {mod_sign})"
        
    return {"title": title_text, "author": {"name": player_name.upper()}, "color": color, "fields": fields_log}

def execute_formula_damage_roll(player_name, dice_input, armor_piercing, macro_label=None):
    try:
        dice_to_roll, global_modifier = parse_dice_string(dice_input)
    except:
        return None, "Error parsing dice string."
    fields_log, damage_grand_total = [], 0
    for count, sides in dice_to_roll:
        for _ in range(abs(count)):
            rolls = roll_single_die(sides)
            total = sum(rolls)
            trail = " -> ".join([f"[{r}]" if r != sides else f"[{r}]💥" for r in rolls])
            damage_grand_total += total
            fields_log.append({"name": f"💥 Damage Die (d{sides})", "value": f"{trail} = **{total}**", "inline": True})
    final_total = damage_grand_total + global_modifier
    mod_sign = f"+{global_modifier}" if global_modifier >= 0 else f"{global_modifier}"
    ap_suffix = f" | 🪓 **AP {armor_piercing}**" if armor_piercing > 0 else ""
    fields_log.append({"name": "📈 Math Breakdown", "value": f"Total ({damage_grand_total}) {mod_sign} = **{final_total}**", "inline": False})
    fields_log.append({"name": "📢 Summary", "value": f"💥 **{final_total} Damage**{ap_suffix}", "inline": False})
    title_text = f"{macro_label} | Damage" if macro_label else f"Damage Roll: {dice_input}"
    return {"title": title_text, "author": {"name": player_name.upper()}, "color": 15158332, "fields": fields_log}, final_total

def send_discord_roll(embed, is_blind=False):
    if is_blind or not DISCORD_WEBHOOK_URL: return True
    payload = {"username": "SWADE Dice Bot", "embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        return True
    except:
        return False

def render_stream_card(embed, is_blind=False):
    st.markdown(f"#### {embed['title']}" + (" 🕵️ [BLIND]" if is_blind else ""))
    st.caption(f"**CHARACTER:** {embed['author']['name']}")
    with st.container(border=True):
        for field in embed['fields']:
            if field['inline']:
                st.write(f"**{field['name']}**: {field['value']}")
            else:
                st.info(f"**{field['name']}**\n\n{field['value']}")

# ==========================================
#     👑 SIDEBAR NAVIGATION INTERFACE 👑
# ==========================================
st.sidebar.title("🎮 GM Operations Desk")
app_mode = st.sidebar.radio("Select Dashboard View:", [
    "🎲 Tactical Dice Console", 
    "🃏 Action Card Dealer (GM)", 
    "📡 Join Live Battle Session (Player)"
])
st.sidebar.markdown("---")

saved_name = local_storage.getItem("swade_player_name") or "Hero"
macro_data = {}
for i in range(1, 7):
    macro_data[f"t_{i}"] = local_storage.getItem(f"swade_m{i}_t") or ""
    macro_data[f"f_{i}"] = local_storage.getItem(f"swade_m{i}_f") or ""
    try:
        macro_data[f"ap_{i}"] = int(local_storage.getItem(f"swade_m{i}_ap") or "0")
    except:
        macro_data[f"ap_{i}"] = 0

with st.sidebar.expander("👤 Character Profile Caching"):
    p_name = st.text_input("Profile Identity Name:", value=saved_name)
    gm_mode = st.checkbox("🔮 Activate GM Shield Mode", value=False)
    st.markdown("**Configure Weapon Macros**")
    t1, t2 = st.tabs(["1-3", "4-6"])
    with t1:
        m1_t, m1_f, m1_ap = st.text_input("M1 Title:", value=macro_data["t_1"]), st.text_input("M1 Formula:", value=macro_data["f_1"]), st.number_input("M1 AP:", value=macro_data["ap_1"], min_value=0)
        m2_t, m2_f, m2_ap = st.text_input("M2 Title:", value=macro_data["t_2"]), st.text_input("M2 Formula:", value=macro_data["f_2"]), st.number_input("M2 AP:", value=macro_data["ap_2"], min_value=0)
        m3_t, m3_f, m3_ap = st.text_input("M3 Title:", value=macro_data["t_3"]), st.text_input("M3 Formula:", value=macro_data["f_3"]), st.number_input("M3 AP:", value=macro_data["ap_3"], min_value=0)
    with t2:
        m4_t, m4_f, m4_ap = st.text_input("M4 Title:", value=macro_data["t_4"]), st.text_input("M4 Formula:", value=macro_data["f_4"]), st.number_input("M4 AP:", value=macro_data["ap_4"], min_value=0)
        m5_t, m5_f, m5_ap = st.text_input("M5 Title:", value=macro_data["t_5"]), st.text_input("M5 Formula:", value=macro_data["f_5"]), st.number_input("M5 AP:", value=macro_data["ap_5"], min_value=0)
        m6_t, m6_f, m6_ap = st.text_input("M6 Title:", value=macro_data["t_6"]), st.text_input("M6 Formula:", value=macro_data["f_6"]), st.number_input("M6 AP:", value=macro_data["ap_6"], min_value=0)
    if st.button("💾 Lock Profile to Browser Memory", use_container_width=True):
        local_storage.setItem("swade_player_name", p_name, key="comb_save_name")
        for i, (t, f, ap) in enumerate([(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)], 1):
            local_storage.setItem(f"swade_m{i}_t", t, key=f"cs_m{i}_t")
            local_storage.setItem(f"swade_m{i}_f", f, key=f"cs_m{i}_f")
            local_storage.setItem(f"swade_m{i}_ap", str(ap), key=f"cs_m{i}_ap")
        st.success("Macros locked!")

# ==========================================
#      VIEW 1: TACTICAL DICE CONSOLE
# ==========================================
if app_mode == "🎲 Tactical Dice Console":
    st.header("🎲 SWADE Tactical Dice Console")
    if not supabase_client:
        st.error("🔌 Cloud Database Link Offline. Check your Streamlit Secrets configurations.")
    
    blind_roll = st.checkbox("🕵️ Blind Roll", value=False) if gm_mode else False
    if blind_roll: st.warning("Privacy Shield Active.")

    st.subheader("🎯 Attack Macros")
    grid = st.columns(2)
    macros = [(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)]
    col_idx = 0
    for t, f, ap in macros:
        if t and f:
            with grid[col_idx % 2]:
                # Split the macro block into a main trigger and a smaller "Load" button
                c_roll, c_load = st.columns([5, 1])
                with c_roll:
                    if st.button(f"⚔️ {t} ({f})", use_container_width=True, key=f"run_{t}_{col_idx}"):
                        emb, tot = execute_formula_damage_roll(p_name, f, ap, macro_label=t)
                        if emb: send_discord_roll(emb, is_blind=blind_roll); st.session_state.roll_history.insert(0, (emb, blind_roll))
                with c_load:
                    if st.button("📥", key=f"load_{col_idx}", help="Load formula into Manual Override to add modifiers"):
                        st.session_state.d_str_input = f
                        st.session_state.d_ap_input = ap
                        st.session_state.manual_mode = "💥 Damage"
                        st.rerun()
            col_idx += 1

    st.markdown("---")
    st.subheader("📋 Manual Override")
    # Link the radio widget directly to our session state tracker
    mode = st.radio("Type:", ["📊 Trait Test", "💥 Damage"], key="manual_mode")
    
    if mode == "📊 Trait Test":
        c1, c2, c3 = st.columns(3)
        with c1: d_die = st.selectbox("Die:", [4, 6, 8, 10, 12], index=2, format_func=lambda x: f"d{x}")
        with c2: s_mod = st.number_input("Mod:", value=0, step=1)
        with c3: act = st.selectbox("Actions:", [1, 2, 3], index=0, format_func=lambda x: f"{x} ({(x-1)*-2} Penalty)")
        f_edge = st.checkbox("Frenzy Edge?", value=False)
        tn = st.number_input("TN:", value=4, step=1)
        if st.button("🎲 Make Trait Roll", type="primary", use_container_width=True):
            emb = execute_dropdown_trait_roll(p_name, d_die, s_mod, (act-1)*-2, tn, is_frenzy=f_edge)
            send_discord_roll(emb, is_blind=blind_roll); st.session_state.roll_history.insert(0, (emb, blind_roll))
    else:
        # These fields now pull directly from the session state if a macro loaded them
        d_str = st.text_input("Formula:", key="d_str_input")
        d_ap = st.number_input("AP:", min_value=0, step=1, key="d_ap_input")
        if st.button("💥 Fire Damage Roll", type="primary", use_container_width=True):
            emb, tot = execute_formula_damage_roll(p_name, d_str, d_ap)
            if emb: send_discord_roll(emb, is_blind=blind_roll); st.session_state.roll_history.insert(0, (emb, blind_roll))

    st.markdown("---")
    st.subheader("📜 Roll History")
    if st.session_state.roll_history:
        if st.button("🗑️ Wipe Feed"): st.session_state.roll_history = []; st.rerun()
        for h_e, h_b in st.session_state.roll_history: render_stream_card(h_e, is_blind=h_b)

# ==========================================
#      VIEW 2: ACTION CARD DEALER (GM DASHBOARD)
# ==========================================
elif app_mode == "🃏 Action Card Dealer (GM)":
    st.header("🃏 Action Card Dealer (GM Control Deck)")
    
    st.session_state.connected_room_code = st.text_input("Campaign Active Room Code:", value="SWAD", max_chars=6).upper()
    
    if st.session_state.joker_drawn: st.error("🚨 JOKER DRAWN! RESHUFFLE NEXT ROUND.")
    st.metric("Cards Remaining in Deck", len(st.session_state.deck))
    
    c_hdr1, c_hdr2 = st.columns([3, 1])
    with c_hdr1:
        st.subheader("👥 Tactical Roster")
    with c_hdr2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Player Joins", use_container_width=True):
            st.rerun()
    
    db_state = pull_room_state(st.session_state.connected_room_code)
    active_pcs = json.loads(db_state.get("player_characters", "[]")) if db_state and db_state.get("player_characters") else []
    active_npcs = json.loads(db_state.get("gm_npcs", "[]")) if db_state and db_state.get("gm_npcs") else []
    
    if p_name and p_name not in active_pcs:
        active_pcs.insert(0, p_name)
        push_rosters_to_db(st.session_state.connected_room_code, active_pcs, active_npcs)
        
    full_roster = active_pcs + active_npcs
    
    clist, cadd = st.columns([2, 1])
    with clist:
        for pc in active_pcs:
            with st.container(border=True):
                r1, r2 = st.columns([5, 1])
                with r1: st.markdown(f"**{pc}** <small>(Player)</small>", unsafe_allow_html=True)
                with r2:
                    if pc != p_name and st.button("🗑️", key=f"d_pc_{pc}"):
                        active_pcs.remove(pc)
                        push_rosters_to_db(st.session_state.connected_room_code, active_pcs, active_npcs)
                        st.rerun()
        for npc in active_npcs:
            with st.container(border=True):
                r1, r2 = st.columns([5, 1])
                with r1: st.markdown(f"**{npc}** <small>(NPC)</small>", unsafe_allow_html=True)
                with r2:
                    if st.button("🗑️", key=f"d_npc_{npc}"):
                        active_npcs.remove(npc)
                        push_rosters_to_db(st.session_state.connected_room_code, active_pcs, active_npcs)
                        st.rerun()

    with cadd:
        n_act = st.text_input("Name:", placeholder="NPC Name...", key="n_act")
        if st.button("➕ Add NPC", use_container_width=True):
            if n_act.strip() and n_act.strip() not in full_roster:
                active_npcs.append(n_act.strip())
                push_rosters_to_db(st.session_state.connected_room_code, active_pcs, active_npcs)
                st.rerun()
                
        st.markdown("---")
        if st.button("🔄 Full Reshuffle", use_container_width=True): shuffle_deck(); st.success("Deck Shuffled!")

    st.markdown("---")
    if st.button("🃏 Deal Cards & Next Round", type="primary", use_container_width=True):
        if full_roster: deal_to_roster(full_roster); st.rerun()

    st.markdown("---")
    st.subheader("📜 Round Manifest")
    
    if st.button("🗑️ Clear Manifest & Reset Rounds", use_container_width=False):
        st.session_state.round_counter = 0
        st.session_state.round_history = []
        st.session_state.current_round_hands = {}
        st.session_state.joker_drawn = False
        
        if supabase_client:
            payload = {"round": 0, "joker_drawn": False, "hands": {}}
            supabase_client.table("combat_sessions").update({
                "sorted_hands": payload,
                "player_characters": json.dumps([]),
                "gm_npcs": json.dumps([])
            }).eq("room_code", st.session_state.connected_room_code).execute()
        st.rerun()

    if st.session_state.round_history:
        st.info("💡 Cards are automatically sorted by SWADE value and suit hierarchy.")
        for r_num, hands_list in st.session_state.round_history:
            with st.expander(f"📅 ROUND {r_num} SUMMARY", expanded=(r_num == st.session_state.round_counter)):
                cols = st.columns(len(hands_list))
                for idx, (name, card) in enumerate(hands_list):
                    with cols[idx]:
                        badge = f"<div style='background-color:#5865f2; color:white; font-size:10px; padding:2px 5px; border-radius:3px; font-weight:bold;'>ACTING #{idx+1}</div>"
                        is_joker = "Joker" in card
                        bg = "#ff4b4b" if is_joker else "#1e1e24"
                        suit_c = "white" if is_joker else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                        st.markdown(f'<div style="background-color:{bg}; text-align:center; padding:12px; border-radius:5px; border:1px solid #4a4a4a; min-height:120px;"><div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:4px; margin-bottom:8px;"><strong style="font-size:11px; color:white; text-transform:uppercase; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:90px;">{name}</strong>{badge}</div><div style="font-size:24px; font-weight:bold; color:{suit_c};">{card}</div></div>', unsafe_allow_html=True)
    else:
        st.caption("Manifest empty. Deal cards to begin Round 1.")

# ==========================================
#      VIEW 3: THE LIVE PLAYER SESSION SYNC OVERVIEW
# ==========================================
else:
    st.header("📡 Live Table Initiative Session Sync")
    
    st.markdown("Enter your active campaign connection parameters below to view the GM's digital card table in real time.")
    
    c_r1, c_r2 = st.columns([1, 2])
    with c_r1:
        target_room = st.text_input("Enter 4-Letter Room Code:", value="SWAD", max_chars=6).upper()
    with c_r2:
        st.markdown("<br>", unsafe_allow_html=True)
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            refresh_trigger = st.button("🔄 Pull Current Table Initiative Status", type="primary", use_container_width=True)
        with c_btn2:
            if st.button("🙋 Join Active Roster", use_container_width=True):
                db_state = pull_room_state(target_room)
                pcs = json.loads(db_state.get("player_characters", "[]")) if db_state and db_state.get("player_characters") else []
                npcs = json.loads(db_state.get("gm_npcs", "[]")) if db_state and db_state.get("gm_npcs") else []
                if p_name not in pcs:
                    pcs.append(p_name)
                    push_rosters_to_db(target_room, pcs, npcs)
                    st.success(f"Deployed {p_name} to the GM's tactical grid! (Tell your GM to sync)")
        
    st.markdown("---")
    
    cloud_data = pull_initiative_from_db(target_room)
    
    if cloud_data and cloud_data.get("hands"):
        r_num = cloud_data.get("round", 1)
        is_j_drawn = cloud_data.get("joker_drawn", False)
        raw_hands = cloud_data.get("hands", {})
        
        hands_dict = dict(sorted(raw_hands.items(), key=lambda item: get_card_weight(item[1]), reverse=True))
        
        st.subheader(f"🎴 Live Round Manifest: Round {r_num}")
        if is_j_drawn:
            st.error("🚨 A JOKER HAS BEEN UNLEASHED THIS ROUND! ALL COMBATANTS REMAIN ON HIGH ALERT. 🚨")
            
        st.caption("Sorted Sequence of Battle Order:")
        
        p_cols = st.columns(len(hands_dict))
        for idx, (name, card) in enumerate(hands_dict.items()):
            with p_cols[idx]:
                badge = f"<div style='background-color:#5865f2; color:white; font-size:10px; padding:2px 5px; border-radius:3px; font-weight:bold;'>ACTING #{idx+1}</div>"
                is_joker = "Joker" in card
                bg = "#ff4b4b" if is_joker else "#1e1e24"
                suit_c = "white" if is_joker else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                
                st.markdown(
                    f"""
                    <div style="background-color:{bg}; text-align:center; padding:16px; border-radius:5px; border:1px solid #4a4a4a; min-height:130px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:6px; margin-bottom:10px;">
                            <strong style="font-size:12px; color:white; text-transform:uppercase; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100px;">{name}</strong>
                            {badge}
                        </div>
                        <div style="font-size:28px; font-weight:bold; color:{suit_c}; margin-top:5px;">{card}</div>
                    </div>
                    """, unsafe_allow_html=True
                )
    else:
        st.warning(f"No active combat dashboard found matching Room Code '{target_room}'. Tell your GM to generate an active deal round first!")
