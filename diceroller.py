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

# Initialize Local Storage Connector
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
        title_text = f"⚡ {macro_label} | {title_text}"

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

# Secure safe fallbacks for Local Storage context parameters
saved_name = local_storage.getItem("swade_player_name") or "Hero"
saved_macro_1 = local_storage.getItem("swade_macro_1") or ""
saved_macro_2 = local_storage.getItem("swade_macro_2") or ""

col_main, col_macro = st.columns([2, 1])

with col_macro:
    st.header("💾 Character Profile")
    p_name = st.text_input("Character Name:", value=saved_name)
    
    st.subheader("⚔️ Custom Weapon Macros")
    m1_val = st.text_input("Macro 1 Title:", value=saved_macro_1, key="m1_t")
    m1_form = st.text_input("Macro 1 Formula:", placeholder="1d10+1d6+2", key="m1_f")
    m1_ap = st.number_input("Macro 1 AP:", value=0, min_value=0, key="m1_ap")
    
    st.markdown("---")
    m2_val = st.text_input("Macro 2 Title:", value=saved_macro_2, key="m2_t")
    m2_form = st.text_input("Macro 2 Formula:", placeholder="2d6", key="m2_f")
    m2_ap = st.number_input("Macro 2 AP:", value=0, min_value=0, key="m2_ap")
    
    if st.button("💾 Save Settings to This Device", use_container_width=True):
        # PATCHED: Explicit contextual isolation keys added to prevent engine element collisions
        local_storage.setItem("swade_player_name", p_name, key="save_storage_name")
        local_storage.setItem("swade_macro_1", m1_val, key="save_storage_m1")
        local_storage.setItem("swade_macro_2", m2_val, key="save_storage_m2")
        st.success("Profile updated securely! Refresh the window to verify parameters.")

with col_main:
    st.header("🎯 Active Battlefield Console")
    
    if m1_val and m1_form:
        if st.button(f"⚔️ Attack via macro: {m1_val} ({m1_form})", use_container_width=True):
            embed, total = execute_formula_damage_roll(p_name, m1_form, m1_ap, macro_label=m1_val)
            if embed:
                send_discord_roll(embed)
                st.success(f"Sent **{total} Damage** to Discord.")
                
    if m2_val and m2_form:
        if st.button(f"🔥 Cast via macro: {m2_val} ({m2_form})", use_container_width=True):
            embed, total = execute_formula_damage_roll(p_name, m2_form, m2_ap, macro_label=m2_val)
            if embed:
                send_discord_roll(embed)
                st.success(f"Sent **{total} Damage** to Discord.")

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
