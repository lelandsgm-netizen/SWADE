import streamlit as st
import random
import requests
from collections import defaultdict

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

def execute_swade_roll(player_name, die_sides, is_trait=True, modifier=0, target_number=4):
    """Executes a full SWADE roll calculation with explosion trails."""
    # 1. Roll Trait Die
    trait_rolls = roll_single_die(die_sides)
    trait_total = sum(trait_rolls)
    
    # 2. Format Trait Visual Trail
    trait_trail = " -> ".join([f"[{r}]" if r != die_sides else f"[{r}]💥" for r in trait_rolls])
    
    wild_total = 0
    wild_trail = ""
    
    # 3. Roll Wild Die if it's a Trait Test
    if is_trait:
        wild_rolls = roll_single_die(6)
        wild_total = sum(wild_rolls)
        wild_trail = " -> ".join([f"[{r}]" if r != 6 else f"[{r}]💥" for r in wild_rolls])
        
        # Determine Higher Die
        final_die_total = max(trait_total, wild_total)
        chosen_type = "Trait Die" if trait_total >= wild_total else "Wild Die"
    else:
        # Damage Roll Mode (Add everything together)
        final_die_total = trait_total
        chosen_type = "Damage Roll"
        
    # 4. Apply Flat Modifiers
    final_total = final_die_total + modifier
    
    # 5. Calculate Success & Raises
    result_text = ""
    embed_color = 9807243  # Default Grey
    
    # Check for Critical Failure (Snake Eyes on Trait + Wild)
    if is_trait and trait_rolls[0] == 1 and wild_rolls[0] == 1:
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

    # 6. Build the Discord Embed Card Layout
    mod_sign = f"+{modifier}" if modifier >= 0 else f"{modifier}"
    title_mode = f"📊 Trait Test: d{die_sides} ({mod_sign})" if is_trait else f"⚔️ Damage Roll: d{die_sides} ({mod_sign})"
    
    embed = {
        "title": title_mode,
        "author": {"name": player_name.upper()},
        "color": embed_color,
        "fields": [
            {"name": "🎲 Trait Die Result", "value": f"{trait_trail} = **{trait_total}**", "inline": True}
        ]
    }
    
    if is_trait:
        embed["fields"].append({"name": "🃏 Wild Die (d6)", "value": f"{wild_trail} = **{wild_total}**", "inline": True})
        embed["fields"].append({"name": "📈 Math Breakdown", "value": f"Higher Die ({final_die_total}) {mod_sign} = **{final_total}**", "inline": False})
    else:
        embed["fields"].append({"name": "📈 Math Breakdown", "value": f"Total ({final_die_total}) {mod_sign} = **{final_total}**", "inline": False})
        
    embed["fields"].append({"name": "📢 Resolution", "value": f"**{result_text}** (vs TN {target_number})", "inline": False})
    
    return embed, result_text, trait_trail, wild_trail, final_total

# --- Web UI Interface Layout ---
st.set_page_config(page_title="SWADE Dice Roller", page_icon="🎲")
st.title("🎲 SWADE Dice Engine")

# App Navigation / Toggle Mode
app_mode = st.radio("Choose App Tool:", ["🃏 Initiative Tracker (Active)", "🎲 Dice Roller Sandbox (Testing)"])

if app_mode == "🃏 Initiative Tracker (Active)":
    st.info("Your primary initiative code is running perfectly backgrounded. Switch to the Dice Roller Sandbox radio button above to test out Phase 1 of our new mechanics!")
else:
    st.subheader("Experimental Dice Console")
    
    # Input Block Configuration
    p_name = st.text_input("Character Name:", value="Hero")
    
    col_d, col_m = st.columns(2)
    with col_d:
        die_choice = st.selectbox("Select Trait Die:", [4, 6, 8, 10, 12], index=2)
    with col_m:
        mod_choice = st.number_input("Flat Modifier (+/-):", value=0, step=1)
        
    roll_type = st.checkbox("Is this a Trait Test? (Uncheck for pure Damage Rolls)", value=True)
    tn_choice = st.number_input("Target Number (TN):", value=4, step=1)

    if st.button("🎲 Fire Roll to Discord", type="primary", use_container_width=True):
        embed, res, t_trail, w_trail, total = execute_swade_roll(
            player_name=p_name, 
            die_sides=die_choice, 
            is_trait=roll_type, 
            modifier=mod_choice, 
            target_number=tn_choice
        )
        
        # Send data to Discord
        send_discord_roll(embed)
        
        # Render visual outcome confirmation box directly on screen
        st.success(f"Roll dispatched successfully! Result: {total} ({res})")
        st.markdown(f"**Your Trait Trail:** {t_trail}")
        if roll_type:
            st.markdown(f"**Your Wild Trail:** {w_trail}")
