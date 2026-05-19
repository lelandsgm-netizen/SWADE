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
    # Clean up spaces
    cleaned = dice_string.lower().replace(" ", "")
    
    # Find all dice expressions (e.g., '1d10', '2d6')
    dice_matches = re.findall(r'([+-]?\d*)d(\d+)', cleaned)
    
    # Remove the dice parts to see what flat modifiers are left
    remainder = re.sub(r'([+-]?\d*)d(\d+)', '', cleaned)
    
    # Calculate final flat modifier
    modifier = 0
    if remainder:
        # Find all trailing numbers with signs
        mod_matches = re.findall(r'([+-]?\d+)', remainder)
        for mod in mod_matches:
            modifier += int(mod)
            
    dice_to_roll = []
    for count_str, sides_str in dice_matches:
        # Default to 1 die if count is omitted (e.g., 'd6' instead of '1d6')
        count = 1
        if count_str and count_str != '+' and count_str != '-':
            count = int(count_str)
        elif count_str == '-':
            count = -1
            
        sides = int(sides_str)
        dice_to_roll.append((count, sides))
        
    return dice_to_roll, modifier

def execute_complex_roll(player_name, dice_input, is_trait=True, target_number=4):
    """Executes a parsed multi-dice rolling calculation."""
    try:
        dice_to_roll, global_modifier = parse_dice_string(dice_input)
    except:
        return None, "Error parsing dice string. Make sure it looks like '1d10+1d6+2'!"

    if not dice_to_roll and global_modifier == 0:
        return None, "Invalid formula! Enter something like '2d6' or 'd8+2'."

    fields_log = []
    highest_trait_total = 0
    damage_grand_total = 0
    all_snakes_eyes = True  # Track for potential critical failure
    
    # --- Execute All Dice Pools ---
    for count, sides in dice_to_roll:
        for _ in range(abs(count)):
            rolls = roll_single_die(sides)
            total = sum(rolls)
            trail = " -> ".join([f"[{r}]" if r != sides else f"[{r}]💥" for r in rolls])
            
            # If any single die roll isn't a 1, we can't critical fail
            if rolls[0] != 1:
                all_snakes_eyes = False
                
            if is_trait:
                # In trait mode, we track the highest single exploding die pool
                if total > highest_trait_total:
                    highest_trait_total = total
                fields_log.append({"name": f"🎲 Trait Die (d{sides})", "value": f"{trail} = **{total}**", "inline": True})
            else:
                # In damage mode, we add everything together directly
                damage_grand_total += total
                fields_log.append({"name": f"⚔️ Damage Die (d{sides})", "value": f"{trail} = **{total}**", "inline": True})

    # --- Handle Wild Die for Trait Tests ---
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
        all_snakes_eyes = False # Damage rolls cannot critical fail in SWADE

    # --- Final Math Calculation ---
    final_total = final_die_base + global_modifier
    mod_sign = f"+{global_modifier}" if global_modifier >= 0 else f"{global_modifier}"
    
    # --- Resolution Status Checking ---
    result_text = ""
    embed_color = 9807243  # Default Grey
    
    if is_trait and all_snakes_eyes and dice_to_roll:
        result_text = "💀 CRITICAL FAILURE! 💀"
        embed_color = 15158332  # Red
    else:
        net_score = final_total - target_number
        if net_score < 0:
            result_text = "Failure"
            embed_color = 9807243  # Grey
        else:
            raises = net_score // 4
            if raises == 0:
                result_text = "🎯 Success!"
                embed_color = 3066993  # Green
            else:
                result_text = f"🔥 Success with {raises} Raise(s)!"
                embed_color = 15105570  # Gold/Orange

    # --- Build the Payload ---
    title_mode = f"📊 Trait Roll: {dice_input}" if is_trait else f"💥 Damage Roll: {dice_input}"
    
    embed = {
        "title": title_mode,
        "author": {"name": player_name.upper()},
        "color": embed_color,
        "fields": fields_log
    }
    
    # Add summary block
    if is_trait:
        embed["fields"].append({"name": "📈 Math Breakdown", "value": f"Higher Die ({final_die_base}) {mod_sign} = **{final_total}**", "inline": False})
    else:
        embed["fields"].append({"name": "📈 Math Breakdown", "value": f"Total ({final_die_base}) {mod_sign} = **{final_total}**", "inline": False})
        
    embed["fields"].append({"name": "📢 Resolution", "value": f"**{result_text}** (vs TN {target_number})", "inline": False})
    
    return embed, result_text, final_total

# --- Web UI Interface Layout ---
st.set_page_config(page_title="SWADE Multi-Dice Roller", page_icon="🎲")
st.title("🎲 SWADE Advanced Dice Console")

p_name = st.text_input("Character Name:", value="Hero")

# Upgraded input block to accept clean text string formulas
dice_input = st.text_input("Enter Roll Formula (e.g., d8, 2d6, 1d10+1d6+2):", value="1d10+1d6")

roll_type = st.checkbox("Is this a Trait Test? (Uncheck for weapon/spell Damage Rolls)", value=False)
tn_choice = st.number_input("Target Number (TN):", value=4, step=1)

if st.button("🎲 Fire Complex Roll to Discord", type="primary", use_container_width=True):
    embed, err_or_res, total = execute_complex_roll(
        player_name=p_name,
        dice_input=dice_input,
        is_trait=roll_type,
        target_number=tn_choice
    )
    
    if embed is None:
        st.error(err_or_res)
    else:
        send_discord_roll(embed)
        st.success(f"Roll processed! Sent total of **{total}** ({err_or_res}) to Discord.")
