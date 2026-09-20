# Sources

Every photograph under `sim/assets/real/` with the licence it carries and the page it came
from. Wikimedia Commons rows name the licence exactly as the file page states it. Openverse
rows name the licence the Openverse index reports for that record.

No photograph here has a person in frame. `bin_1.jpg`, `bin_2.jpg` and `bin_3.jpg` are the bin
backgrounds: the inside of a crumpled black liner, which is what the phone sees when the bin is
empty. `bin.png` is `bin_1.jpg` resized to the phone's 640 px width and saved under the name the
phone simulator looks for; it is the same photograph, not a new one. `sprites/` holds every item
photograph resized to 220 px on the long side, which is the size the item is composited at
inside a 640 px frame, so the bench and the scenario feed the model the same picture.

`keyboard_1_tagged.jpg`, and its sprite, are `keyboard_1.jpg` with a printed BB-0002 QR label
pasted on, built the way `sim/make_assets.py` builds the drawn keyboard's: a 104 px code on a
10 px white quiet zone, on the right hand side, at the same module size. `demo_real.yaml` uses
the tagged one so the register write the demo turns on actually happens. It is a derived file,
not a new photograph, so it has no row of its own; the row for `keyboard_1.jpg` covers it and
that file is untouched.

One row per photograph, 42 rows.

| File | Item | Title | Author | Licence | Page |
|---|---|---|---|---|---|
| `bagel_1.jpg` | bagel | File:Plain-Bagel.jpg | Evan-Amos | Public domain | https://commons.wikimedia.org/wiki/File:Plain-Bagel.jpg |
| `bagel_2.jpg` | bagel | File:Bagel-Plain-Alt.jpg | Evan-Amos | Public domain | https://commons.wikimedia.org/wiki/File:Bagel-Plain-Alt.jpg |
| `bagel_3.jpg` | bagel | File:2019-10-12 15 29 40 A Thomas Plain Bagel in the Dulles section of Sterling, Loudoun County, Virginia.jpg | Famartin | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:2019-10-12_15_29_40_A_Thomas_Plain_Bagel_in_the_Dulles_section_of_Sterling,_Loudoun_County,_Virginia.jpg |
| `half_sandwich_1.jpg` | half_sandwich | File:Fluffer Nutter Sandwich.jpg | User:SGT9hJGI | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Fluffer_Nutter_Sandwich.jpg |
| `half_sandwich_2.jpg` | half_sandwich | File:Half eaten ham sandwich.jpg | Punker1999 | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Half_eaten_ham_sandwich.jpg |
| `banana_1.jpg` | banana | File:Liat Portal for Foodie Disorder - Banana.jpg | HaJunkiyada | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Liat_Portal_for_Foodie_Disorder_-_Banana.jpg |
| `banana_2.jpg` | banana | File:Radiant Red Bananas By Raju C Reddy.jpg | rajucreddy | CC0 | https://commons.wikimedia.org/wiki/File:Radiant_Red_Bananas_By_Raju_C_Reddy.jpg |
| `apple_1.jpg` | apple | File:Granny Smith Apples.jpg | not stated | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Granny_Smith_Apples.jpg |
| `apple_2.jpg` | apple | Apple a day | Ruanon | BY-SA 2.0 | https://www.flickr.com/photos/70873497@N02/6935006104 |
| `soda_can_1.jpg` | soda_can | File:HK 堅尼地城 Kennedy Town Coca Cola red can body October 2019 SS2 02.jpg | Gdragoo Joehp fcore | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:HK_%E5%A0%85%E5%B0%BC%E5%9C%B0%E5%9F%8E_Kennedy_Town_Coca_Cola_red_can_body_October_2019_SS2_02.jpg |
| `soda_can_2.jpg` | soda_can | File:HK soft drink 芬達 Fanta Orange Flavoured Soda n metal can easy pull ring key October 2024 R12S 01.jpg | Shunfeng 2088 WEIA | CC0 | https://commons.wikimedia.org/wiki/File:HK_soft_drink_%E8%8A%AC%E9%81%94_Fanta_Orange_Flavoured_Soda_n_metal_can_easy_pull_ring_key_October_2024_R12S_01.jpg |
| `soda_can_3.jpg` | soda_can | File:HK soft drink 芬達 Fanta Orange Flavoured Soda n metal can easy pull ring key October 2024 R12S 02.jpg | Shunfeng 2088 WEIA | CC0 | https://commons.wikimedia.org/wiki/File:HK_soft_drink_%E8%8A%AC%E9%81%94_Fanta_Orange_Flavoured_Soda_n_metal_can_easy_pull_ring_key_October_2024_R12S_02.jpg |
| `water_bottle_1.jpg` | water_bottle | File:Glaceau Smartwater 20oz bottle.jpg | Benjamin Ikuta | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Glaceau_Smartwater_20oz_bottle.jpg |
| `water_bottle_2.jpg` | water_bottle | File:Evian Bottle.jpg | James Tamim | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Evian_Bottle.jpg |
| `coffee_cup_1.jpg` | coffee_cup | File:SJ mugg.jpg | Unknown author Unknown author | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:SJ_mugg.jpg |
| `coffee_cup_2.jpg` | coffee_cup | File:Disposable paper coffee cup at Kakadu Crocodile Hotel, Jabiru, Northern Territory, 2021.jpg | Kgbo | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Disposable_paper_coffee_cup_at_Kakadu_Crocodile_Hotel,_Jabiru,_Northern_Territory,_2021.jpg |
| `coffee_cup_3.jpg` | coffee_cup | File:The Cat’s Pyjamas exceedingly fancy coffee with Covid Safe Sugar in Gundog Espresso, Nyngan, NSW, 2021.jpg | Kgbo | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:The_Cat%E2%80%99s_Pyjamas_exceedingly_fancy_coffee_with_Covid_Safe_Sugar_in_Gundog_Espresso,_Nyngan,_NSW,_2021.jpg |
| `pizza_slice_1.jpg` | pizza_slice | File:Fat Slice pepperoni pizza slice.JPG | BrokenSphere | CC BY 3.0 | https://commons.wikimedia.org/wiki/File:Fat_Slice_pepperoni_pizza_slice.JPG |
| `pizza_slice_2.jpg` | pizza_slice | File:Slice House Pizza Pepperoni slice (43899573075).jpg | Willis Lam | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Slice_House_Pizza_Pepperoni_slice_(43899573075).jpg |
| `cardboard_box_1.jpg` | cardboard_box | File:Cardboard box with office supplies.jpg | Oneupweb | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Cardboard_box_with_office_supplies.jpg |
| `cardboard_box_2.jpg` | cardboard_box | File:Corrugated box - haz mat.jpg | Rlsheehan ( talk ) | Public domain | https://commons.wikimedia.org/wiki/File:Corrugated_box_-_haz_mat.jpg |
| `keyboard_1.jpg` | keyboard | File:Mechanical keyboard example.jpg | Thanasis Termitzoglou | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Mechanical_keyboard_example.jpg |
| `keyboard_2.jpg` | keyboard | File:2018 Bay Area Mechanical Keyboard Meetup (31008008287).jpg | Patrick Breen | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:2018_Bay_Area_Mechanical_Keyboard_Meetup_(31008008287).jpg |
| `usbc_charger_1.jpg` | usbc_charger | File:Apple 5W USB Power Adapter (4935).jpg | Gregory Varnum | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Apple_5W_USB_Power_Adapter_(4935).jpg |
| `usbc_charger_2.jpg` | usbc_charger | File:Apple USB Charger 1 2017-02-02.jpg | F ASTILY | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Apple_USB_Charger_1_2017-02-02.jpg |
| `usbc_charger_3.jpg` | usbc_charger | File:Pisen MF-08EU 12W USB charger-4.jpg | Imgrenb | CC0 | https://commons.wikimedia.org/wiki/File:Pisen_MF-08EU_12W_USB_charger-4.jpg |
| `laptop_charger_1.jpg` | laptop_charger | File:Lenovo Power Adapter AC 65W 20V.jpg | Neozoon | CC0 | https://commons.wikimedia.org/wiki/File:Lenovo_Power_Adapter_AC_65W_20V.jpg |
| `laptop_charger_2.jpg` | laptop_charger | File:Yhi power adapter observe.jpg | Rjluna2 | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Yhi_power_adapter_observe.jpg |
| `laptop_charger_3.jpg` | laptop_charger | File:Lenovo Power Adapter AC 135W 20V.jpg | Neozoon | CC0 | https://commons.wikimedia.org/wiki/File:Lenovo_Power_Adapter_AC_135W_20V.jpg |
| `mouse_1.jpg` | mouse | File:Wireless mouse.jpg | Door man | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Wireless_mouse.jpg |
| `mouse_2.jpg` | mouse | File:Wireless Logilink Computer mouse with USB Micro Dongle.JPG | Mattes | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Wireless_Logilink_Computer_mouse_with_USB_Micro_Dongle.JPG |
| `earbuds_1.jpg` | earbuds | File:ActiveSound wireless earbuds by Hykker (POJM200483).jpg | Warszawska róg Szerokiej w Tomaszowie Mazowieckim, w województwie łódzkim, PL, EU | Public domain | https://commons.wikimedia.org/wiki/File:ActiveSound_wireless_earbuds_by_Hykker_(POJM200483).jpg |
| `earbuds_2.jpg` | earbuds | File:Yamaha TW-E3A Earbuds Customize, Japan; April 2021 (01).jpg | MIKI Yoshihito. (#mikiyoshihito) | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Yamaha_TW-E3A_Earbuds_Customize,_Japan;_April_2021_(01).jpg |
| `phone_cracked_1.jpg` | phone_cracked | File:Samsung Galaxy S2 shattered screen.jpg | Ashwin Kumar from Bangalore, India | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Samsung_Galaxy_S2_shattered_screen.jpg |
| `phone_cracked_2.jpg` | phone_cracked | File:Smartphone cracked screen.jpg | Sygmoral | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Smartphone_cracked_screen.jpg |
| `power_bank_1.jpg` | power_bank | File:Canyon Power Bank 4400 mAh.jpg | Чибас 333 | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Canyon_Power_Bank_4400_mAh.jpg |
| `power_bank_2.jpg` | power_bank | File:Power Bank Phantom 13000mAh.jpg | JETE Official | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Power_Bank_Phantom_13000mAh.jpg |
| `hdmi_cable_1.jpg` | hdmi_cable | File:Cable HDMI 1.4, rizado 0775.jpg | Electronicgrup | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Cable_HDMI_1.4,_rizado_0775.jpg |
| `hdmi_cable_2.jpg` | hdmi_cable | File:HDMI Cable 1.JPG | Kannan shanmugam,shanmugam studio, Kollam | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:HDMI_Cable_1.JPG |
| `bin_1.jpg` | background | Crumpled black garbage bag texture | Teddy | CC0 1.0 | https://www.rawpixel.com/image/6164469/crumpled-black-garbage-bag-texture-background |
| `bin_2.jpg` | background | Crumpled black garbage bag texture | Teddy | CC0 1.0 | https://www.rawpixel.com/image/6170277/crumpled-black-garbage-bag-texture-background |
| `bin_3.jpg` | background | Crumpled black garbage bag texture | Teddy | CC0 1.0 | https://www.rawpixel.com/image/6170780/crumpled-black-garbage-bag-texture-background |
