import streamlit as st
import random
import requests
import re
from streamlit_local_storage import LocalStorage

# --- Global Page Configuration ---
st.set_page_config(page_title="SWADE Master Toolkit", page_icon="🃏", layout="wide")

# Initialize Local Storage Connector
local_storage = LocalStorage()

# --- Sync Server Secrets Safely ---
if "DISCORD_WEBHOOK_URL" in st.secrets:
    DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]
else:
    DISCORD_WEBHOOK_URL = None

# --- Persistent Session State Configuration ---
# This guarantees your card deck doesn't auto-wipe when navigating between pages!
if "deck" not in st.session_state:
    st.session_state.deck = []
if "discard" not in st.session_state:
    st.session_state.discard = []
if "hand" not in st.session_state:
    st.session_state.hand = []
if "joker_drawn" not in st.session_state:
    st.session_state.joker_drawn = False
if "roll_history" not in st.session_state:
    st.session_state.roll_history = []

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
    st.session_state.hand = []
    st.session_state.joker_drawn = False

if not st.session_state.deck and not st.session_state.discard:
    shuffle_deck()

def draw_cards(num):
    drawn = []
    for _ in range(num):
        if not st.session_state.deck:
            break
        card = st.session_state.deck.pop(0)
        drawn.append(card)
        if "Joker" in card:
            st.session_state.joker_drawn = True
    st.session_state.hand = drawn
    st.session_state.discard.extend(drawn)

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
            base_die = 0
            final_total = 0
        else:
            base_die = max(trait_total, wild_total)
            final_total = base_die + total_modifier
            res_text, color = calculate_resolution(final_total, target_number)
            
        breakdown_text = f"Highest Die ({base_die})"
        if situational_mod != 0:
            breakdown_text += f" + Sit Mod ({situational_mod})"
        if map_penalty != 0:
            breakdown_text += f" + MAP Penalty ({map_penalty})"
        breakdown_text += f" = **{final_total}**"
        
        fields_log.append({"name": "📈 Math Breakdown", "value": breakdown_text, "inline": False})
        fields_log.append({"name": "📢 Resolution", "value": f"**{res_text}** (vs TN {target_number})", "inline": False})
        title_text = f"📊 Trait Test: d{die_sides} (Net Mod: {mod_sign})"
    else:
        t1_rolls = roll_single_die(die_sides)
        t1_total = sum(t1_rolls)
        t1_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t1_rolls])
        
        t2_rolls = roll_single_die(die_sides)
        t2_total = sum(t2_rolls)
        t2_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t2_rolls])
        
        fields_log.append({"name": "⚔️ Attack Die #1", "value": f"{t1_trail} = **{t1_total}**", "inline": True})
        fields_log.append({"name": "⚔️ Attack Die #2", "value": f"{t2_trail} = **{t2_total}**", "inline": True})
        fields_log.append({"name": "🃏 Shared Wild Die", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        
        if t1_rolls[0] == 1 and t2_rolls[0] == 1 and wild_rolls[0] == 1:
            fields_log.append({"name": "🚨 COMBAT DISASTER", "value": "💀 **CRITICAL FAILURE ON BOTH ATTACKS!** 💀", "inline": False})
            color = 15158332
        else:
            pairs_a = [t1_total, t2_total]
            pairs_b = [wild_total, t2_total]
            pairs_c = [t1_total, wild_total]
            best_combo = max([pairs_a, pairs_b, pairs_c], key=lambda x: (sum(x), max(x)))
            
            final_atk1 = best_combo[0] + total_modifier
            final_atk2 = best_combo[1] + total_modifier
            res1, _ = calculate_resolution(final_atk1, target_number)
            res2, _ = calculate_resolution(final_atk2, target_number)
            
            penalty_breakdown = ""
            if situational_mod != 0:
                penalty_breakdown += f" + Sit Mod ({situational_mod})"
            if map_penalty != 0:
                penalty_breakdown += f" + MAP Penalty ({map_penalty})"

            fields_log.append({"name": "⚔️ Attack #1 Outcome", "value": f"Base ({best_combo[0]}){penalty_breakdown} = **{final_atk1}**\n↳ **{res1}**", "inline": False})
            fields_log.append({"name": "⚔️ Attack #2 Outcome", "value": f"Base ({best_combo[1]}){penalty_breakdown} = **{final_atk2}**\n↳ **{res2}**", "inline": False})
            color = 15105570
            
        title_text = f"⚔️ Frenzy Full Attack: 2x d{die_sides} (Net Mod: {mod_sign})"
        
    embed = {
        "title": title_text,
        "author": {"name": player_name.upper()},
        "color": color,
        "fields": fields_log
    }
    return embed

def execute_formula_damage_roll(player_name, dice_input, armor_piercing, macro_label=None):
    try:
        dice_to_roll, global_modifier = parse_dice_string(dice_input)
    except:
        return None, "Error parsing dice string. Make sure it looks like '1d10+1d6+2'!"

    if not dice_to_roll and global_modifier == 0:
        return None, "Invalid formula! Enter something like '2d6' or 'd8+2'."

    fields_log = []
    damage_grand_total = 0
    
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
    
    title_text = f"Damage Roll: {dice_input}"
    if macro_label:
        title_text = f"{macro_label} | {title_text}"

    embed = {
        "title": title_text,
        "author": {"name": player_name.upper()},
        "color": 15158332,
        "fields": fields_log
    }
    return embed, final_total

def send_discord_roll(embed, is_blind=False):
    if is_blind or not DISCORD_WEBHOOK_URL:
        return True
    payload = {"username": "SWADE Dice Bot", "embeds": [embed]}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        return response.status_code == 204
    except:
        return False

def render_stream_card(embed, is_blind=False):
    blind_suffix = " 🕵️ [BLIND ROLL]" if is_blind else ""
    st.markdown(f"#### {embed['title']}{blind_suffix}")
    st.caption(f"**CHARACTER:** {embed['author']['name']}")
    with st.container(border=True):
        for field in embed['fields']:
            if field['inline']:
                st.write(f"**{field['name']}**: {field['value']}")
            else:
                st.info(f"**{field['name']}**\n\n{field['value']}")
    st.markdown(" ")

# ==========================================
#     👑 SIDEBAR NAVIGATION INTERFACE 👑
# ==========================================
st.sidebar.title("🎮 GM Operations Desk")
app_mode = st.sidebar.radio("Select Dashboard View:", ["🎲 Tactical Dice Console", "🃏 Action Card Dealer"])

st.sidebar.markdown("---")

# Load device local storage data profiles
saved_name = local_storage.getItem("swade_player_name") or "Hero"
macro_data = {}
for i in range(1, 7):
    macro_data[f"t_{i}"] = local_storage.getItem(f"swade_m{i}_t") or ""
    macro_data[f"f_{i}"] = local_storage.getItem(f"swade_m{i}_f") or ""
    saved_ap = local_storage.getItem(f"swade_m{i}_ap") or "0"
    try:
        macro_data[f"ap_{i}"] = int(saved_ap)
    except:
        macro_data[f"ap_{i}"] = 0

# Render Configuration Panel under navigation
with st.sidebar.expander("👤 Character Profile Caching"):
    p_name = st.text_input("Profile Identity Name:", value=saved_name)
    gm_mode = st.checkbox("🔮 Activate GM Shield Mode", value=False)
    
    st.markdown("**Configure Weapon Macros**")
    t_1, t_2 = st.tabs(["Macros 1-3", "Macros 4-6"])
    with t_1:
        m1_t = st.text_input("M1 Title:", value=macro_data["t_1"])
        m1_f = st.text_input("M1 Formula:", value=macro_data["f_1"])
        m1_ap = st.number_input("M1 AP:", value=macro_data["ap_1"], min_value=0)
        m2_t = st.text_input("M2 Title:", value=macro_data["t_2"])
        m2_f = st.text_input("M2 Formula:", value=macro_data["f_2"])
        m2_ap = st.number_input("M2 AP:", value=macro_data["ap_2"], min_value=0)
        m3_t = st.text_input("M3 Title:", value=macro_data["t_3"])
        m3_f = st.text_input("M3 Formula:", value=macro_data["f_3"])
        m3_ap = st.number_input("M3 AP:", value=macro_data["ap_3"], min_value=0)
    with t_2:
        m4_t = st.text_input("M4 Title:", value=macro_data["t_4"])
        m4_f = st.text_input("M4 Formula:", value=macro_data["f_4"])
        m4_ap = st.number_input("M4 AP:", value=macro_data["ap_4"], min_value=0)
        m5_t = st.text_input("M5 Title:", value=macro_data["t_5"])
        m5_f = st.text_input("M5 Formula:", value=macro_data["f_5"])
        m5_ap = st.number_input("M5 AP:", value=macro_data["ap_5"], min_value=0)
        m6_t = st.text_input("M6 Title:", value=macro_data["t_6"])
        m6_f = st.text_input("M6 Formula:", value=macro_data["f_6"])
        m6_ap = st.number_input("M6 AP:", value=macro_data["ap_6"], min_value=0)
        
    if st.button("💾 Lock Profile to Browser Memory", use_container_width=True):
        local_storage.setItem("swade_player_name", p_name, key="comb_save_name")
        for idx, (t, f, ap) in enumerate([(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)], 1):
            local_storage.setItem(f"swade_m{idx}_t", t, key=f"comb_save_m{idx}_t")
            local_storage.setItem(f"swade_m{idx}_f", f, key=f"comb_save_m{idx}_f")
            local_storage.setItem(f"swade_m{idx}_ap", str(ap), key=f"comb_save_m{idx}_ap")
        st.success("Macros locked! Refresh window to update.")

# ==========================================
#      VIEW 1: TACTICAL DICE CONSOLE
# ==========================================
if app_mode == "🎲 Tactical Dice Console":
    st.header("🎲 SWADE Tactical Dice Console")
    
    blind_roll = False
    if gm_mode:
        blind_roll = st.checkbox("🕵️ Blind Roll (Calculate locally, hide from Discord)", value=False)
        if blind_roll:
            st.warning("Privacy Shield Active: Results stream below in secret.")

    st.subheader("🎯 Custom Attack Macros")
    grid_cols = st.columns(2)
    macro_slots = [(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), 
                   (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)]
    
    col_idx = 0
    for title, formula, ap in macro_slots:
        if title and formula:
            with grid_cols[col_idx % 2]:
                if st.button(f"⚔️ Fire Attack: {title} ({formula})", use_container_width=True, key=f"comb_run_{title}_{col_idx}"):
                    embed, total = execute_formula_damage_roll(p_name, formula, ap, macro_label=title)
                    if embed:
                        send_discord_roll(embed, is_blind=blind_roll)
                        st.session_state.roll_history.insert(0, (embed, blind_roll))
            col_idx += 1
            
    if col_idx == 0:
        st.info("No macros active. Configure them inside the sidebar profile tab.")

    st.markdown("---")
    st.subheader("📋 Manual Override Deck")
    roll_mode = st.radio("Select Combat Action:", ["📊 Trait Test", "💥 Weapon/Spell Damage"])

    if roll_mode == "📊 Trait Test":
        c1, c2, c3 = st.columns(3)
        with c1:
            die_choice = st.selectbox("Select Trait Die:", [4, 6, 8, 10, 12], index=2, format_func=lambda x: f"d{x}")
        with c2:
            mod_choice = st.number_input("Situational Modifiers (+/-):", value=0, step=1)
        with c3:
            action_intent = st.selectbox("Multi-Action Count This Turn:", [1, 2, 3], index=0, 
                                         format_func=lambda x: f"{x} Action (0 Penalty)" if x == 1 else (f"{x} Actions (-2 Penalty)" if x == 2 else f"{x} Actions (-4 Penalty)"))
            
        map_penalty = 0 if action_intent == 1 else (-2 if action_intent == 2 else -4)
        frenzy_selection = st.checkbox("Apply Frenzy Edge? (2x Attacks via 1 Shared Wild Die)", value=False)
        tn_choice = st.number_input("Target Number (TN):", value=4, step=1)

        if st.button("🎲 Make Trait Roll", type="primary", use_container_width=True):
            embed = execute_dropdown_trait_roll(p_name, die_choice, mod_choice, map_penalty, tn_choice, is_frenzy=frenzy_selection)
            send_discord_roll(embed, is_blind=blind_roll)
            st.session_state.roll_history.insert(0, (embed, blind_roll))
    else:
        dice_input = st.text_input("Enter Damage Formula String:", value="1d10+1d6")
        ap_choice = st.number_input("Armor Piercing Factor:", value=0, min_value=0, step=1)

        if st.button("💥 Fire Damage Roll", type="primary", use_container_width=True):
            embed, total = execute_formula_damage_roll(p_name, dice_input, ap_choice)
            if embed:
                send_discord_roll(embed, is_blind=blind_roll)
                st.session_state.roll_history.insert(0, (embed, blind_roll))

    st.markdown("---")
    st.subheader("📜 Live Action Roll Log")
    if st.session_state.roll_history:
        if st.button("🗑️ Wipe Active Feed Log"):
            st.session_state.roll_history = []
            st.rerun()
        for h_emb, h_bl in st.session_state.roll_history:
            render_stream_card(h_emb, is_blind=h_bl)
    else:
        st.caption("Dice dashboard silent. Roll results stream here live.")

# ==========================================
#      VIEW 2: ACTION CARD DEALER
# ==========================================
else:
    st.header("🃏 SWADE Action Card Dealer")
    
    # Render global turn indicators
    if st.session_state.joker_drawn:
        st.error("🚨 A JOKER WAS DRAWN THIS ROUND! RESHUFFLE MANDATORY FOR NEXT TURN. 🚨")
        
    st.metric("Cards Remaining in Action Deck", len(st.session_state.deck))
    
    c1, c2 = st.columns(2)
    with c1:
        draw_count = st.number_input("Number of Combatants Drawing Cards:", min_value=1, max_value=15, value=1)
        if st.button("🃏 Deal Turn Cards", type="primary", use_container_width=True):
            draw_cards(draw_count)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Complete Deck Reset & Shuffle", use_container_width=True):
            shuffle_deck()
            st.success("Deck completely gathered, cleared, and thoroughly shuffled!")

    if st.session_state.hand:
        st.markdown("---")
        st.subheader("🎴 Current Round Turn Card Manifest")
        
        # Display cards horizontally for easy grouping
        card_cols = st.columns(len(st.session_state.hand))
        for idx, card in enumerate(st.session_state.hand):
            with card_cols[idx]:
                if "Joker" in card:
                    st.markdown(f"⚡ **[COMBATANT #{idx+1}]**\n<div style='font-size:32px; background-color:#ff4b4b; text-align:center; padding:15px; border-radius:5px; color:white; font-weight:bold;'>{card}</div>", unsafe_allow_html=True)
                else:
                    color = "#2f3136"
                    if '♥' in card or '♦' in card:
                        text_color = "#ff4b4b"
                    else:
                        text_color = "#ffffff"
                    st.markdown(f"👤 **[COMBATANT #{idx+1}]**\n<div style='font-size:32px; background-color:{color}; color:{text_color}; text-align:center; padding:15px; border-radius:5px; border:1px solid #4a4a4a;'>{card}</div>", unsafe_allow_html=True)
