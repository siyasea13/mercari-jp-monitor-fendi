import asyncio
import smtplib
import time  
from email.message import EmailMessage
from mercapi import Mercapi

# --- CONFIGURATION ---
CHECK_INTERVAL = 300  
EMAIL_SENDER = "siyashahh13@gmail.com"
EMAIL_PASSWORD = "tkqi xxgb qinu ottm"  
EMAIL_RECEIVER = "siyashahh13@gmail.com"

SEARCH_PARAMS = {
    "query": "",
    "categories": [208],
    "brands": [1026]
}

seen_item_ids = set()

async def send_email(item, item_id):
    msg = EmailMessage()
    msg.set_content(f"New item found!\n\nName: {item.name}\nPrice: {item.price}\nURL: https://jp.mercari.com/item/{item_id}")
    msg['Subject'] = f"🔔 Mercari Alert: {item.name}"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"--> Notification sent for: {item.name}")
    except Exception as e:
        print(f"--> Failed to send email: {e}")

async def poll_mercari():
    global seen_item_ids 
    
    m = Mercapi()
    
    # Record start time (minus a 5-minute safety buffer for timezone weirdness)
    bot_start_time = int(time.time()) - 300
    
    print("Starting Mercari monitor...")
    print("STATUS: 'Birth Certificate' verification active. Hunting ghosts...")
    
    is_first_run = True
    
    while True:
        try:
            results = await m.search(**SEARCH_PARAMS)
            
            for item in results.items:
                # 1. Ignore obviously sold items
                status_str = str(getattr(item, 'status', '')).upper()
                if 'SOLD_OUT' in status_str or 'TRADING' in status_str:
                    continue
                    
                item_id = getattr(item, 'id_', getattr(item, 'item_id', getattr(item, 'product_id', 'UNKNOWN_ID')))
                if item_id == 'UNKNOWN_ID':
                    continue 

                if item_id not in seen_item_ids:
                    seen_item_ids.add(item_id)
                    
                    if is_first_run:
                        continue # Silently memorize the first page

                    # --- THE BIRTH CERTIFICATE CHECK ---
                    try:
                        # Bot clicks the specific item to get the FULL hidden data
                        full_item = await m.item(item_id)
                        item_time = getattr(full_item, 'created', getattr(full_item, 'updated', 0))
                        
                        # Validate the time
                        if isinstance(item_time, (int, float)) and item_time > 0:
                            if item_time > 9999999999: 
                                item_time = item_time / 1000
                                
                            if item_time < bot_start_time:
                                print(f"[BLOCKED GHOST]: {item.name} (This is actually an old item)")
                                continue 
                        else:
                            print(f"[BLOCKED]: Couldn't verify time for {item.name}. Skipping to be safe.")
                            continue # FAIL CLOSED: If we don't know the time, trash it.

                        # If it survives all checks, it's a true drop!
                        print(f"*** TRUE NEW DROP ***: {item.name}")
                        await send_email(full_item, item_id)
                        
                    except Exception as e:
                        print(f"Error inspecting item {item_id}: {e}")
                    
                    # Be gentle on Mercari's servers so we don't get IP banned
                    await asyncio.sleep(1)
            
            is_first_run = False
            
            if len(seen_item_ids) > 1000:
                seen_item_ids = set(list(seen_item_ids)[-500:])

        except Exception as e:
            print(f"Error during poll: {e}")
            
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(poll_mercari())
