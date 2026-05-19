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
        if roll == sides:
            continue
        break
    return rolls

def parse_dice_string(dice_string):
    """Parses complex strings like '1d10+1d6+2' into components."""
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
    """Calculates success, failure, or raises against a target number."""
    net = total - tn
    if net < 0:
        return "Failure", 9807243
    else:
        raises = net // 4
        return ("🎯 Success!" if raises == 0 else f"🔥 Success with {raises} Raise(s)!"), (3066993 if raises == 0 else 15105570)

# --- Processing Engines ---
def execute_dropdown_trait_roll(player_name, die_sides, modifier, target_number, is_frenzy=False):
    """Executes a Trait Test. If Frenzy is active, resolves two separate attack totals using one Wild Die."""
    fields_log = []
    mod_sign = f"+{modifier}" if modifier >= 0 else f"{modifier}"
    
    # --- 1. Roll the Wild Die ---
    wild_rolls = roll_single_die(6)
    wild_total = sum(wild_rolls)
    wild_trail = " -> ".join([f"[{r}]" if r != 6 else f"[{r}]💥" for r in wild_rolls])
    
    if not is_frenzy:
        # Standard Single Attack Logic
        trait_rolls = roll_single_die(die_sides)
        trait_total = sum(trait_rolls)
        trait_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in trait_rolls])
        
        fields_log.append({"name": f"🎲 Trait Die (d{die_sides})", "value": f"{trait_trail} = **{trait_total}**", "inline": True})
        fields_log.append({"name": "🃏 Wild Die (d6)", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        
        is_snake_eyes = (trait_rolls[0] == 1 and wild_rolls[0] == 1)
        
        if is_snake_eyes:
            res_text, color = "💀 CRITICAL FAILURE! 💀", 15158332
            final_total = trait_total + modifier # placeholder math for display
        else:
            base_die = max(trait_total, wild_total)
            final_total = base_die + modifier
            res_text, color = calculate_resolution(final_total, target_number)
            
        fields_log.append({"name": "📈 Math Breakdown", "value": f"Higher Die ({base_die}) {mod_sign} = **{final_total}**", "inline": False})
        fields_log.append({"name": "📢 Resolution", "value": f"**{res_text}** (vs TN {target_number})", "inline": False})
        title_text = f"📊 Trait Test: d{die_sides} ({mod_sign})"
        
    else:
        # --- True SWADE Frenzy Multi-Attack Logic ---
        t1_rolls = roll_single_die(die_sides)
        t1_total = sum(t1_rolls)
        t1_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t1_rolls])
        
        t2_rolls = roll_single_die(die_sides)
        t2_total = sum(t2_rolls)
        t2_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in t2_rolls])
        
        fields_log.append({"name": "⚔️ Attack Die #1", "value": f"{t1_trail} = **{t1_total}**", "inline": True})
        fields_log.append({"name": "⚔️ Attack Die #2", "value": f"{t2_trail} = **{t2_total}**", "inline": True})
        fields_log.append({"name": "🃏 Shared Wild Die", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        
        # Check for Critical Failure (Both attack dice AND wild die must roll a 1)
        if t1_rolls[0] == 1 and t2_rolls[0] == 1 and wild_rolls[0] == 1:
            fields_log.append({"name": "🚨 COMBAT DISASTER", "value": "💀 **CRITICAL FAILURE ON BOTH ATTACKS!** 💀", "inline": False})
            color = 15158332
        else:
            # Smart allocation: assign Wild Die to whichever attack path benefits most
            # Path A: Keep normal pairings
            pairs_a = [t1_total, t2_total]
            # Path B: Wild die replaces Attack 1
            pairs_b = [wild_total, t2_total]
            # Path C: Wild die replaces Attack 2
            pairs_c = [t1_total, wild_total]
            
            # Find the best combination option that maximizes both attack totals
            best_combo = max([pairs_a, pairs_b, pairs_c], key=lambda x: (sum(x), max(x)))
            
            final_atk1 = best_combo[0] + modifier
            final_atk2 = best_combo[1] + modifier
            
            res1, _ = calculate_resolution(final_atk1, target_number)
            res2, _ = calculate_resolution(final_atk2, target_number)
            
            fields_log.append({
                "name": "⚔️ Attack #1 Outcome", 
                "value": f"Base ({best_combo[0]}) {mod_sign} = **{final_atk1}**\n↳ **{res1}**", 
                "inline": False
            })
            fields_log.append({
                "name": "⚔️ Attack #2 Outcome", 
                "value": f"Base ({best_combo[1]}) {mod_sign} = **{final_atk2}**\n↳ **{res2}**", 
                "inline": False
            })
            color = 15105570  # Aggressive combat gold theme
            
        title_text = f"⚔️ Frenzy Full Attack: 2x d{die_sides} ({mod_sign})"
        final_total = 0 # Dummy value for function return layout
        
    embed = {
        "title": title_text,
        "author": {"name": player_name.upper()},
        "color": color,
        "fields": fields_log
    }
    return embed, final_total

def execute_formula_damage_roll(player_name, dice_input, armor_piercing):
    """Executes a parsed multi-dice weapon damage calculation."""
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
    
    embed = {
        "title": f"⚔️ Damage Roll: {dice_input}",
        "author": {"name": player_name.upper()},
        "color": 15158332,
        "fields": fields_log
    }
    return embed, final_total

# --- Web UI Interface Layout ---
st.set_page_config(page_title="SWADE Premium Roller", page_icon="🎲")
st.title("🎲 SWADE Tactical Dice Console")

p_name = st.text_input("Character Name:", value="Hero")
roll_mode = st.radio("Select Action Type:", ["📊 Trait Test (Skill/Attribute)", "💥 Weapon/Spell Damage"])

st.markdown("---")

if roll_mode == "📊 Trait Test (Skill/Attribute)":
    col_d, col_m = st.columns(2)
    with col_d:
        die_choice = st.selectbox("Select Trait Die:", [4, 6, 8, 10, 12], index=2, format_func=lambda x: f"d{x}")
    with col_m:
        mod_choice = st.number_input("Flat Modifier (+/-):", value=0, step=1)
        
    tn_choice = st.number_input("Target Number (TN):", value=4, step=1)
    
    # Updated to true rule specification
    frenzy_selection = st.checkbox("Apply Frenzy Edge? (2x Attacks via 1 Shared Wild Die)", value=False)

    if st.button("🎲 Fire Trait Test to Discord", type="primary", use_container_width=True):
        embed, _ = execute_dropdown_trait_roll(
            player_name=p_name,
            die_sides=die_choice,
            modifier=mod_choice,
            target_number=tn_choice,
            is_frenzy=frenzy_selection
        )
        send_discord_roll(embed)
        st.success(f"Trait test dispatched successfully to Discord!")

else:
    dice_input = st.text_input("Enter Damage Formula (e.g., 2d6, 1d10+1d6+2):", value="1d10+1d6")
    ap_choice = st.number_input("Weapon Armor Piercing (AP):", value=0, step=1, min_value=0)

    if st.button("💥 Fire Damage Roll to Discord", type="primary", use_container_width=True):
        embed, total = execute_formula_damage_roll(
            player_name=p_name,
            dice_input=dice_input,
            armor_piercing=ap_choice
        )
        if embed is None:
            st.error(total)
        else:
            send_discord_roll(embed)
            ap_msg = f" (AP {ap_choice})" if ap_choice > 0 else ""
            st.success(f"Damage roll sent! Total: **{total} Damage**{ap_msg}")
