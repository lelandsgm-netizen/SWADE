import streamlit as st
import random
import requests
import re
from streamlit_local_storage import LocalStorage

# --- Global Page Configuration ---
st.set_page_config(page_title="SWADE Master Toolkit", page_icon="🃏", layout="wide")

local_storage = LocalStorage()

if "DISCORD_WEBHOOK_URL" in st.secrets:
    DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]
else:
    DISCORD_WEBHOOK_URL = None

# --- Persistent Session State Configuration ---
if "deck" not in st.session_state:
    st.session_state.deck = []
if "discard" not in st.session_state:
    st.session_state.discard = []
if "joker_drawn" not in st.session_state:
    st.session_state.joker_drawn = False
if "roll_history" not in st.session_state:
    st.session_state.roll_history = []
if "manual_combatants" not in st.session_state:
    st.session_state.manual_combatants = [] 

# Combat Round Tracking States
if "round_counter" not in st.session_state:
    st.session_state.round_counter = 0
if "round_history" not in st.session_state:
    st.session_state.round_history = [] 
if "current_round_hands" not in st.session_state:
    st.session_state.current_round_hands = {} # Core fixed memory container for active UI display

# ==========================================
#      CARD DEALER ENGINE ENGINE CORES
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
    """Assigns an absolute rule-accurate SWADE hierarchy value to any given card string."""
    if "Joker" in card_str:
        return 9999 # Jokers dominate completely
    
    val_part = card_str[:-1]
    suit_part = card_str[-1]
    
    value_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit_map = {'♠':4, '♥':3, '♦':2, '♣':1} # Spades > Hearts > Diamonds > Clubs
    
    # PATCHED: Multiplied face values by 100 so raw card number always dictates order over suit strings
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
            
    # Sort hands perfectly by corrected weight values
    sorted_hands = dict(sorted(hands.items(), key=lambda item: get_card_weight(item[1]), reverse=True))
    
    st.session_state.round_counter += 1
    st.session_state.current_round_hands = sorted_hands
    
    # Store complete round snapshot as a list of item tuples to protect internal scope integrity
    st.session_state.round_history.insert(0, (st.session_state.round_counter, list(sorted_hands.items())))
    st.session_state.discard.extend(sorted_hands.values())
    
    send_initiative_to_discord(sorted_hands, st.session_state.round_counter)

def send_initiative_to_discord(sorted_hands, round_num):
    if not DISCORD_WEBHOOK_URL:
        return
    fields = []
    for idx, (actor_name, card_value) in enumerate(sorted_hands.items(), 1):
        status = "ACTING FIRST" if idx == 1 else f"Turn Order #{idx}"
        if "Joker" in card_value:
            status = "🃏 JOKER (Actions +2 / Toughness +2)"
        fields.append({"name": f"{idx}. {actor_name.upper()}", "value": f"Card: **{card_value}**\n*{status}*", "inline": False})
        
    embed = {
        "title": f"⚔️ Initiative Dispatched: Round {round_num}",
        "color": 3447003,
        "fields": fields
    }
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
        if roll == sides:
            continue
        break
    return rolls

def parse_dice_string(dice_string):
    cleaned = dice_string.lower().replace(" ", "")
    dice_matches = re.findall(r'([+-]?\d*)d(\d+)', cleaned)
    remainder = re.sub(r'([+-]?\d*)d(\d+)', '', cleaned)
    modifier = 0
    if remainder:
        mod_matches = re.findall(r'([+-]?\d+)', remainder)
        for mod in mod_matches:
            modifier += int(mod)
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
    if is_blind or not DISCORD_WEBHOOK_URL:
        return True
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
app_mode = st.sidebar.radio("Select Dashboard View:", ["🎲 Tactical Dice Console", "🃏 Action Card Dealer"])
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
            local_storage.setItem(f"swade_m{i}_t", t, key=f"cs_m{i}_t"); local_storage.setItem(f"swade_m{i}_f", f, key=f"cs_m{i}_f"); local_storage.setItem(f"swade_m{i}_ap", str(ap), key=f"cs_m{i}_ap")
        st.success("Macros locked!")

# ==========================================
#      VIEW 1: TACTICAL DICE CONSOLE
# ==========================================
if app_mode == "🎲 Tactical Dice Console":
    st.header("🎲 SWADE Tactical Dice Console")
    blind_roll = st.checkbox("🕵️ Blind Roll", value=False) if gm_mode else False
    if blind_roll: st.warning("Privacy Shield Active.")

    st.subheader("🎯 Attack Macros")
    grid = st.columns(2)
    macros = [(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)]
    col_idx = 0
    for t, f, ap in macros:
        if t and f:
            with grid[col_idx % 2]:
                if st.button(f"⚔️ {t} ({f})", use_container_width=True, key=f"run_{t}_{col_idx}"):
                    emb, tot = execute_formula_damage_roll(p_name, f, ap, macro_label=t)
                    if emb: send_discord_roll(emb, is_blind=blind_roll); st.session_state.roll_history.insert(0, (emb, blind_roll))
            col_idx += 1

    st.markdown("---")
    st.subheader("📋 Manual Override")
    mode = st.radio("Type:", ["📊 Trait Test", "💥 Damage"])
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
        d_str = st.text_input("Formula:", value="1d10+1d6")
        d_ap = st.number_input("AP:", value=0, min_value=0, step=1)
        if st.button("💥 Fire Damage Roll", type="primary", use_container_width=True):
            emb, tot = execute_formula_damage_roll(p_name, d_str, d_ap)
            if emb: send_discord_roll(emb, is_blind=blind_roll); st.session_state.roll_history.insert(0, (emb, blind_roll))

    st.markdown("---")
    st.subheader("📜 Roll History")
    if st.session_state.roll_history:
        if st.button("🗑️ Wipe Feed"): st.session_state.roll_history = []; st.rerun()
        for h_e, h_b in st.session_state.roll_history: render_stream_card(h_e, is_blind=h_b)

# ==========================================
#      VIEW 2: ACTION CARD DEALER (FIXED MANIFEST)
# ==========================================
else:
    st.header("🃏 Action Card Dealer")
    if st.session_state.joker_drawn: st.error("🚨 JOKER DRAWN! RESHUFFLE NEXT ROUND.")
    st.metric("Cards Remaining", len(st.session_state.deck))
    
    st.subheader("👥 Tactical Roster")
    full_roster = [p_name] + st.session_state.manual_combatants
    clist, cadd = st.columns([2, 1])
    with clist:
        for idx, actor in enumerate(full_roster):
            with st.container(border=True):
                r1, r2 = st.columns([5, 1])
                with r1: st.markdown(f"**{actor}** <small>({'Player' if idx==0 else 'NPC'})</small>", unsafe_allow_html=True)
                with r2:
                    if idx > 0 and st.button("🗑️", key=f"d_{idx}"): st.session_state.manual_combatants.pop(idx-1); st.rerun()
    with cadd:
        n_act = st.text_input("Name:", placeholder="NPC Name...", key="n_act")
        if st.button("➕ Add NPC", use_container_width=True):
            if n_act.strip() and n_act not in full_roster: st.session_state.manual_combatants.append(n_act.strip()); st.rerun()
        st.markdown("---")
        if st.button("🔄 Full Reshuffle", use_container_width=True): shuffle_deck(); st.success("Deck Shuffled!")

    st.markdown("---")
    if st.button("🃏 Deal Cards & Next Round", type="primary", use_container_width=True):
        if full_roster: deal_to_roster(full_roster); st.rerun()

    # --- THE ROUND MANIFEST ---
    st.markdown("---")
    st.subheader("📜 Round Manifest")
    
    if st.button("🗑️ Clear Manifest & Reset Rounds", use_container_width=False):
        st.session_state.round_counter = 0
        st.session_state.round_history = []
        st.session_state.current_round_hands = {}
        st.session_state.joker_drawn = False
        st.rerun()

    if st.session_state.round_history:
        st.info("💡 Cards are automatically sorted by SWADE value and suit hierarchy (Spades > Hearts > Diamonds > Clubs).")
        
        # FIX: Explicit structural loops targeting structured scope definitions for layout stability
        for r_num, hands_list in st.session_state.round_history:
            with st.expander(f"📅 ROUND {r_num} SUMMARY", expanded=(r_num == st.session_state.round_counter)):
                cols = st.columns(len(hands_list))
                for idx, (name, card) in enumerate(hands_list):
                    with cols[idx]:
                        # Visual Logic: Display proper ACTING # sequence string (1-indexed base)
                        badge = f"<div style='background-color:#5865f2; color:white; font-size:10px; padding:2px 5px; border-radius:3px; font-weight:bold;'>ACTING #{idx+1}</div>"
                        is_joker = "Joker" in card
                        bg = "#ff4b4b" if is_joker else "#1e1e24"
                        suit_c = "white" if is_joker else ("#ff4b4b" if ('♥' in card or '♦' in card) else "white")
                        
                        st.markdown(
                            f"""
                            <div style="background-color:{bg}; text-align:center; padding:12px; border-radius:5px; border:1px solid #4a4a4a; min-height:120px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:4px; margin-bottom:8px;">
                                    <strong style="font-size:11px; color:white; text-transform:uppercase; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:90px;">{name}</strong>
                                    {badge}
                                </div>
                                <div style="font-size:24px; font-weight:bold; color:{suit_c};">{card}</div>
                            </div>
                            """, unsafe_allow_html=True
                        )
    else:
        st.caption("Manifest empty. Deal cards to begin Round 1.")
