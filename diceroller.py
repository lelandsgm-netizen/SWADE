import streamlit as st
import random
import requests
import re

# --- Configuration ---
if "DISCORD_WEBHOOK_URL" in st.secrets:
    DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]
else:
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1316953166142771272/2Tmz3vk-Vvb7bcxTmqZfYPJI7y4r7jssH8X1Rs9cQSN2owvroBpOfsuUAtGypPBxC6Ik"

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
    """Rolls a single die and handles infinite exploding Aces."""
    rolls = []
    while True:
        roll = random.randint(1, sides)
        rolls.append(roll)
        if roll == sides:  # It's an Ace! Explode!
            continue
        break
    return rolls

def parse_dice_string(dice_string):
    """Parses complex strings like '1d10+1d6+2' or '2d6' into components."""
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

def execute_complex_roll(player_name, dice_input, is_trait=True, target_number=4, armor_piercing=0):
    """Executes a parsed multi-dice rolling calculation with smart SWADE rule resolution."""
    try:
        dice_to_roll, global_modifier = parse_dice_string(dice_input)
    except:
        return None, "Error parsing dice string. Make sure it looks like '1d10+1d6+2'!"

    if not dice_to_roll and global_modifier == 0:
        return None, "Invalid formula! Enter something like '2d6' or 'd8+2'."

    fields_log = []
    highest_trait_total = 0
    damage_grand_total = 0
    all_snakes_eyes = True
    
    # --- Execute All Dice Pools ---
    for count, sides in dice_to_roll:
        for _ in range(abs(count)):
            rolls = roll_single_die(sides)
            total = sum(rolls)
            trail = " -> ".join([f"[{r}]" if r != sides else f"[{r}]💥" for r in rolls])
            
            if rolls[0] != 1:
                all_snakes_eyes = False
                
            if is_trait:
                if total > highest_trait_total:
                    highest_trait_total = total
                fields_log.append({"name": f"🎲 Trait Die (d{sides})", "value": f"{trail} = **{total}**", "inline": True})
            else:
                damage_grand_total += total
                fields_log.append({"name": f"⚔️ Damage Die (d{sides})", "value": f"{trail} = **{total}**", "inline": True})

    # --- Handle Wild Die vs Pure Damage Layout ---
    wild_total = 0
    if is_trait:
        wild_rolls = roll_single_die(6)
        wild_total = sum(wild_rolls)
        wild_trail = " -> ".join([f"[{r}]" if r != 6 else f"[{r}]💥" for r in wild_rolls])
        
        if wild_rolls[0] != 1:
            all_snakes_eyes = False
            
        fields_log.append({"name": "🃏 Wild Die (d6)", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        final_die_base = max(highest_trait_total, wild_total)
    else:
        final_die_base = damage_grand_total
        all_snakes_eyes = False

    # --- Final Calculations ---
    final_total = final_die_base + global_modifier
    mod_sign = f"+{global_modifier}" if global_modifier >= 0 else f"{global_modifier}"
    
    # --- Build the Payload ---
    if is_trait:
        title_mode = f"📊 Trait Roll: {dice_input}"
        # Evaluate rules resolution metrics for Trait Tests
        if all_snakes_eyes and dice_to_roll:
            result_text = "💀 CRITICAL FAILURE! 💀"
            embed_color = 15158332  # Red
        else:
            net_score = final_total - target_number
            if net_score < 0:
                result_text = "Failure"
                embed_color = 9807243  # Grey
            else:
                raises = net_score // 4
                result_text = "🎯 Success!" if raises == 0 else f"🔥 Success with {raises} Raise(s)!"
                embed_color = 3066993 if raises == 0 else 15105570
                
        fields_log.append({"name": "📈 Math Breakdown", "value": f"Higher Die ({final_die_base}) {mod_sign} = **{final_total}**", "inline": False})
        fields_log.append({"name": "📢 Resolution", "value": f"**{result_text}** (vs TN {target_number})", "inline": False})
    else:
        # Damage Roll Layout (Completely drops TN and Success text)
        title_mode = f"💥 Damage Roll: {dice_input}"
        embed_color = 15158332  # Dynamic combat red styling for impact
        
        ap_suffix = f" | 🪓 **AP {armor_piercing}**" if armor_piercing > 0 else ""
        
        fields_log.append({"name": "📈 Math Breakdown", "value": f"Total ({final_die_base}) {mod_sign} = **{final_total}**", "inline": False})
        fields_log.append({"name": "📢 Summary", "value": f"💥 **{final_total} Damage**{ap_suffix}", "inline": False})
    
    embed = {
        "title": title_mode,
        "author": {"name": player_name.upper()},
        "color": embed_color,
        "fields": fields_log
    }
    
    return embed, final_total

# --- Web UI Interface Layout ---
st.set_page_config(page_title="SWADE Dice Roller", page_icon="🎲")
st.title("🎲 SWADE Advanced Dice Console")

p_name = st.text_input("Character Name:", value="Hero")
dice_input = st.text_input("Enter Roll Formula (e.g., d8, 2d6, 1d10+1d6+2):", value="1d10+1d6")

# The central toggle that changes the configuration context
roll_type = st.checkbox("Is this a Trait Test? (Check for Skills/Attributes, Uncheck for Damage)", value=False)

# Clean, dynamically rendering input boxes depending on what mode is active
if roll_type:
    tn_choice = st.number_input("Target Number (TN):", value=4, step=1)
    ap_choice = 0
else:
    tn_choice = 4
    ap_choice = st.number_input("Weapon Armor Piercing (AP):", value=0, step=1, min_value=0)

if st.button("🎲 Fire Roll to Discord", type="primary", use_container_width=True):
    embed, total = execute_complex_roll(
        player_name=p_name,
        dice_input=dice_input,
        is_trait=roll_type,
        target_number=tn_choice,
        armor_piercing=ap_choice
    )
    
    if embed is None:
        st.error(total)
    else:
        send_discord_roll(embed)
        if roll_type:
            st.success(f"Trait Test sent to Discord! Total: **{total}**")
        else:
            ap_msg = f" (AP {ap_choice})" if ap_choice > 0 else ""
            st.success(f"Damage roll sent to Discord! Total: **{total} Damage**{ap_msg}")
