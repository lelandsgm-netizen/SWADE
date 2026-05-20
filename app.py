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
if "hand_dict" not in st.session_state:
    st.session_state.hand_dict = {}  
if "joker_drawn" not in st.session_state:
    st.session_state.joker_drawn = False
if "roll_history" not in st.session_state:
    st.session_state.roll_history = []
if "manual_combatants" not in st.session_state:
    st.session_state.manual_combatants = [] 

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
    st.session_state.hand_dict = {}
    st.session_state.joker_drawn = False

if not st.session_state.deck and not st.session_state.discard:
    shuffle_deck()

def get_card_weight(card_str):
    """Assigns an absolute rule-accurate SWADE hierarchy value to any given card string."""
    if "Joker" in card_str:
        return 999  # Jokers completely dominate any standard deal hierarchy
    
    # Extract structural value and suit strings securely
    val_part = card_str[:-1]
    suit_part = card_str[-1]
    
    value_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit_map = {'♠':4, '♥':3, '♦':2, '♣':1} # SWADE Suit Priority: Spades > Hearts > Diamonds > Clubs
    
    return (value_map.get(val_part, 0) * 10) + suit_map.get(suit_part, 0)

def deal_to_roster(roster_list):
    current_round_hands = {}
    for actor in roster_list:
        if not st.session_state.deck:
            break
        card = st.session_state.deck.pop(0)
        current_round_hands[actor] = card
        if "Joker" in card:
            st.session_state.joker_drawn = True
            
    st.session_state.hand_dict = current_round_hands
    st.session_state.discard.extend(current_round_hands.values())
    
    # Dynamic Sorting Execution: Rearrange structure from highest card weight down to lowest card weight
    sorted_hands = dict(sorted(current_round_hands.items(), key=lambda item: get_card_weight(item[1]), reverse=True))
    st.session_state.hand_dict = sorted_hands
    
    # DISCORD INTEGRATION: Broadcast Sorted Turn Cards out to the Table Channel
    send_initiative_to_discord(sorted_hands)

def send_initiative_to_discord(sorted_hands):
    """Dispatches a clean, structured turn layout embed table directly into your Discord channel."""
    if not DISCORD_WEBHOOK_URL:
        return
        
    fields = []
    for idx, (actor_name, card_value) in enumerate(sorted_hands.items(), 1):
        prefix = "🔥 [ACTING FIRST]" if idx == 1 else f"Turn #{idx}"
        if "Joker" in card_value:
            prefix = "🃏 [JOKER - FREE RERUN]"
        fields.append({
            "name": f"{idx}. {actor_name.upper()}",
            "value": f"Dealt Initiative Card: **{card_value}**\n↳ Context: *{prefix}*",
            "inline": False
        })
        
    embed = {
        "title": "⚔️ Tactical Turn Order Dispatched!",
        "description": "The initiative card deck has been dealt and sorted by rule hierarchy.",
        "color": 3447003, # Deep Tactical Blue Embed
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
    st.header("🃏 SWADE Active Roster Card Dealer")
    
    if st.session_state.joker_drawn:
        st.error("🚨 A JOKER WAS DRAWN THIS ROUND! RESHUFFLE MANDATORY FOR NEXT ROUND. 🚨")
        
    st.metric("Cards Remaining in Action Deck", len(st.session_state.deck))
    
    st.subheader("👥 Tactical Combat Roster")
    full_combat_roster = [p_name] + st.session_state.manual_combatants
    
    col_list, col_add = st.columns([2, 1])
    
    with col_list:
        st.markdown("**Current Active Turn Order Roster:**")
        for idx, actor in enumerate(full_combat_roster):
            type_tag = "🎭 Player Hero" if idx == 0 else "⚔️ NPC / Monster"
            with st.container(border=True):
                r_c1, r_c2 = st.columns([5, 1])
                with r_c1:
                    st.markdown(f"**{actor}** &nbsp;|&nbsp; <small style='color:#8e9297;'>{type_tag}</small>", unsafe_allow_html=True)
                with r_c2:
                    if idx > 0: 
                        if st.button("🗑️", key=f"del_{idx}_{actor}"):
                            st.session_state.manual_combatants.pop(idx - 1)
                            st.rerun()
                    else:
                        st.caption("🔒 Static")
                        
    with col_add:
        st.markdown("**Add Roster Reinforcements:**")
        new_actor = st.text_input("Enter Combatant Name:", placeholder="Goblin Chieftain, Boss...", key="add_actor_name")
        if st.button("➕ Inject Combatant to Roster", use_container_width=True):
            if new_actor.strip() and new_actor not in full_combat_roster:
                st.session_state.manual_combatants.append(new_actor.strip())
                st.rerun()
                
        st.markdown("---")
        if st.button("🔄 Complete Deck Reset & Shuffle", use_container_width=True):
            shuffle_deck()
            st.success("Deck completely gathered, cleared, and thoroughly shuffled!")

    st.markdown("---")
    if st.button("🃏 Deal Cards & Determine Initiative Order", type="primary", use_container_width=True):
        if full_combat_roster:
            deal_to_roster(full_combat_roster)
            st.rerun()

    # --- UPGRADED AUTO-SORTED DISPLAY MANIFEST ---
    if st.session_state.hand_dict:
        st.markdown("### 🎴 Current Round Turn Card Manifest")
        st.info("💡 **Initiative Resolved:** Cards have been automatically sorted from highest down to lowest to establish the exact sequence of play left-to-right.")
        
        card_cols = st.columns(len(st.session_state.hand_dict))
        
        for idx, (actor_name, card_value) in enumerate(st.session_state.hand_dict.items()):
            with card_cols[idx]:
                # Assign visual badge numbers directly to the card graphics
                turn_badge = f"<span style='background-color:#5865f2; font-size:11px; padding:2px 6px; border-radius:3px; font-weight:bold; color:white;'>ACTING #{idx}</span>"
                
                if "Joker" in card_value:
                    st.markdown(
                        f"""
                        <div style="background-color:#ff4b4b; text-align:center; padding:16px; border-radius:5px; color:white; font-family:sans-serif; min-height:140px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                            <div style="margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.3); padding-bottom:6px;">
                                <strong style="font-size:13px; text-transform:uppercase; letter-spacing:0.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100px;">{actor_name}</strong>
                                <span style='background-color:#f1c40f; color:#111; font-size:10px; padding:2px 5px; border-radius:3px; font-weight:bold;'>💥 JOKER</span>
                            </div>
                            <div style="font-size:32px; font-weight:bold; margin:14px 0;">{card_value}</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                else:
                    bg_box = "#1e1e24"
                    suit_color = "#ff4b4b" if ('♥' in card_value or '♦' in card_value) else "#ffffff"
                    st.markdown(
                        f"""
                        <div style="background-color:{bg_box}; text-align:center; padding:16px; border-radius:5px; border:1px solid #4a4a4a; font-family:sans-serif; min-height:140px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
                            <div style="margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #4a4a4a; padding-bottom:6px;">
                                <strong style="font-size:13px; text-transform:uppercase; color:#b9bbbe; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100px;">{actor_name}</strong>
                                {turn_badge}
                            </div>
                            <div style="font-size:32px; font-weight:bold; color:{suit_color}; margin:14px 0;">{card_value}</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
