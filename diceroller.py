import streamlit as st
import random
import requests
import re
import json
from streamlit_local_storage import LocalStorage

# --- Configuration ---
if "DISCORD_WEBHOOK_URL" in st.secrets:
    DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]
else:
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1316953166142771272/2Tmz3vk-Vvb7bcxTmqZfYPJI7y4r7jssH8X1Rs9cQSN2owvroBpOfsuUAtGypPBxC6Ik"

local_storage = LocalStorage()

# --- Webhook Transmission ---
def send_discord_roll(embed):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {"username": "SWADE Dice Bot", "embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except:
        pass

# --- Core Rolling Logic ---
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

# --- Processing Engines ---
def execute_dropdown_trait_roll(player_name, die_sides, situational_mod, map_penalty, target_number):
    fields_log = []
    total_modifier = situational_mod + map_penalty
    mod_sign = f"+{total_modifier}" if total_modifier >= 0 else f"{total_modifier}"
    
    trait_rolls = roll_single_die(die_sides)
    trait_total = sum(trait_rolls)
    trait_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in trait_rolls])
    
    wild_rolls = roll_single_die(6)
    wild_total = sum(wild_rolls)
    wild_trail = " -> ".join([f"[{r}]" if r != 6 else f"[{r}]💥" for r in wild_rolls])
    
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

    embed = {
        "title": f"📊 Trait Test: d{die_sides} (Net Mod: {mod_sign})",
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
    
    title_text = f"⚔️ Damage Roll: {dice_input}"
    if macro_label:
        title_text = f"⚔️ {macro_label} | {title_text}"

    embed = {
        "title": title_text,
        "author": {"name": player_name.upper()},
        "color": 15158332,
        "fields": fields_log
    }
    return embed, final_total

# --- Web UI Interface Layout ---
st.set_page_config(page_title="SWADE Premium Roller", page_icon="🎲", layout="wide")
st.title("🎲 SWADE Tactical Dice Console")

# Secure safe fallbacks for Local Storage parameters across all 6 slots
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

col_main, col_macro = st.columns([2, 1])

with col_macro:
    st.header("💾 Character Configuration")
    p_name = st.text_input("Character Name:", value=saved_name)
    
    st.subheader("⚔️ Manage Attack Macros")
    
    # Use clean tab layouts to keep 6 macros organized and slick
    tab1, tab2, tab3 = st.tabs(["Macros 1-2", "Macros 3-4", "Macros 5-6"])
    
    with tab1:
        st.markdown("**Slot #1**")
        m1_t = st.text_input("Title:", value=macro_data["t_1"], key="in_m1_t")
        m1_f = st.text_input("Formula (e.g., 2d6):", value=macro_data["f_1"], key="in_m1_f", placeholder="2d6")
        m1_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_1"], min_value=0, key="in_m1_ap")
        st.markdown("---")
        st.markdown("**Slot #2**")
        m2_t = st.text_input("Title:", value=macro_data["t_2"], key="in_m2_t")
        m2_f = st.text_input("Formula (e.g., 1d10+1d6):", value=macro_data["f_2"], key="in_m2_f", placeholder="1d10+1d6")
        m2_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_2"], min_value=0, key="in_m2_ap")
        
    with tab2:
        st.markdown("**Slot #3**")
        m3_t = st.text_input("Title:", value=macro_data["t_3"], key="in_m3_t")
        m3_f = st.text_input("Formula:", value=macro_data["f_3"], key="in_m3_f", placeholder="d6+2")
        m3_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_3"], min_value=0, key="in_m3_ap")
        st.markdown("---")
        st.markdown("**Slot #4**")
        m4_t = st.text_input("Title:", value=macro_data["t_4"], key="in_m4_t")
        m4_f = st.text_input("Formula:", value=macro_data["f_4"], key="in_m4_f", placeholder="2d8")
        m4_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_4"], min_value=0, key="in_m4_ap")
        
    with tab3:
        st.markdown("**Slot #5**")
        m5_t = st.text_input("Title:", value=macro_data["t_5"], key="in_m5_t")
        m5_f = st.text_input("Formula:", value=macro_data["f_5"], key="in_m5_f", placeholder="3d6")
        m5_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_5"], min_value=0, key="in_m5_ap")
        st.markdown("---")
        st.markdown("**Slot #6**")
        m6_t = st.text_input("Title:", value=macro_data["t_6"], key="in_m6_t")
        m6_f = st.text_input("Formula:", value=macro_data["f_6"], key="in_m6_f", placeholder="1d12+2")
        m6_ap = st.number_input("Armor Piercing (AP):", value=macro_data["ap_6"], min_value=0, key="in_m6_ap")
        
    if st.button("💾 Save Profile to This Device", use_container_width=True):
        local_storage.setItem("swade_player_name", p_name, key="save_st_name")
        local_storage.setItem("swade_m1_t", m1_t, key="save_st_m1_t")
        local_storage.setItem("swade_m1_f", m1_f, key="save_st_m1_f")
        local_storage.setItem("swade_m1_ap", str(m1_ap), key="save_st_m1_ap")
        
        local_storage.setItem("swade_m2_t", m2_t, key="save_st_m2_t")
        local_storage.setItem("swade_m2_f", m2_f, key="save_st_m2_f")
        local_storage.setItem("swade_m2_ap", str(m2_ap), key="save_st_m2_ap")
        
        local_storage.setItem("swade_m3_t", m3_t, key="save_st_m3_t")
        local_storage.setItem("swade_m3_f", m3_f, key="save_st_m3_f")
        local_storage.setItem("swade_m3_ap", str(m3_ap), key="save_st_m3_ap")
        
        local_storage.setItem("swade_m4_t", m4_t, key="save_st_m4_t")
        local_storage.setItem("swade_m4_f", m4_f, key="save_st_m4_f")
        local_storage.setItem("swade_m4_ap", str(m4_ap), key="save_st_m4_ap")
        
        local_storage.setItem("swade_m5_t", m5_t, key="save_st_m5_t")
        local_storage.setItem("swade_m5_f", m5_f, key="save_st_m5_f")
        local_storage.setItem("swade_m5_ap", str(m5_ap), key="save_st_m5_ap")
        
        local_storage.setItem("swade_m6_t", m6_t, key="save_st_m6_t")
        local_storage.setItem("swade_m6_f", m6_f, key="save_st_m6_f")
        local_storage.setItem("swade_m6_ap", str(m6_ap), key="save_st_m6_ap")
        
        st.success("All 6 macros saved! Refresh page to update shortcuts.")

with col_main:
    st.header("🎯 Combat Weapon Macros")
    
    # Dynamically map out quick-fire buttons for any active slots
    grid_cols = st.columns(2)
    macro_slots = [(m1_t, m1_f, m1_ap), (m2_t, m2_f, m2_ap), (m3_t, m3_f, m3_ap), 
                   (m4_t, m4_f, m4_ap), (m5_t, m5_f, m5_ap), (m6_t, m6_f, m6_ap)]
    
    col_idx = 0
    for title, formula, ap in macro_slots:
        if title and formula:
            with grid_cols[col_idx % 2]:
                if st.button(f"⚔️ Fire: {title} ({formula})", use_container_width=True, key=f"btn_run_{title}_{col_idx}"):
                    embed, total = execute_formula_damage_roll(p_name, formula, ap, macro_label=title)
                    if embed:
                        send_discord_roll(embed)
                        st.success(f"Dispatched **{total} Damage** to Discord.")
            col_idx += 1
            
    if col_idx == 0:
        st.info("No weapon macros active yet. Configure slots on the right panel to generate shortcut buttons!")

    st.markdown("---")
    st.markdown("### Manual Dashboard Override")
    roll_mode = st.radio("Select Action Type:", ["📊 Trait Test (Skill/Attribute)", "💥 Weapon/Spell Damage"])

    if roll_mode == "📊 Trait Test (Skill/Attribute)":
        col_d, col_m, col_a = st.columns(3)
        with col_d:
            die_choice = st.selectbox("Select Trait Die:", [4, 6, 8, 10, 12], index=2, format_func=lambda x: f"d{x}")
        with col_m:
            mod_choice = st.number_input("Bonuses / Cover Modifiers:", value=0, step=1)
        with col_a:
            action_intent = st.selectbox("Declared Actions This Turn:", [1, 2, 3], index=0, 
                                         format_func=lambda x: f"{x} Action ('0' Penalty)" if x == 1 else (f"{x} Actions ('-2' Penalty)" if x == 2 else f"{x} Actions ('-4' Penalty)"))
            
        map_penalty = 0 if action_intent == 1 else (-2 if action_intent == 2 else -4)
        tn_choice = st.number_input("Target Number (TN):", value=4, step=1)

        if st.button("🎲 Fire Trait Test to Discord", type="primary", use_container_width=True):
            embed = execute_dropdown_trait_roll(p_name, die_choice, mod_choice, map_penalty, tn_choice)
            send_discord_roll(embed)
            st.success("Trait roll processed and dispatched to Discord!")

    else:
        dice_input = st.text_input("Enter Damage Formula:", value="1d10+1d6")
        ap_choice = st.number_input("Weapon Armor Piercing (AP):", value=0, step=1, min_value=0)

        if st.button("💥 Fire Damage Roll to Discord", type="primary", use_container_width=True):
            embed, total = execute_formula_damage_roll(p_name, dice_input, ap_choice)
            if embed is None:
                st.error(total)
            else:
                send_discord_roll(embed)
                st.success(f"Damage roll sent! Total: **{total} Damage**")
