import os

# Sukuriame aplanką testiniams failams
os.makedirs("test_data", exist_ok=True)

# --- Tiekėjas 1 (su variantais ir parametrais) ---
supplier1_ext = """<?xml version="1.0" encoding="UTF-8"?>
<products>
  <product>
    <id>1001</id>
    <name>Grisport trekking shoes</name>
    <description>Comfortable waterproof trekking shoes for men.</description>
    <category>Footwear/Trekking</category>
    <delivery>3</delivery>
    <url>https://b2bsportswholesale.net/public/storage/productimages/91/2f/9f/f0/1775999/image/xlarge_clean.jpg</url>
    <parameters>
      <parameter name="Material">Leather</parameter>
      <parameter name="Color">Brown</parameter>
    </parameters>
    <stock>
      <item option="20752" ean="4058823396622" uid="1">0</item>
      <item option="20753" ean="4058823396615" uid="2">5</item>
    </stock>
  </product>
</products>
"""

supplier1_light = """<?xml version="1.0" encoding="UTF-8"?>
<data>
  <o i="1001">
    <p c="EUR" r="25.00" w="20.00" />
    <v i="20752">0</v>
    <v i="20753">5</v>
  </o>
</data>
"""

# --- Tiekėjas 2 (su papildomomis nuotraukomis) ---
supplier2 = """<?xml version="1.0" encoding="UTF-8"?>
<products>
  <item>
    <prod_id>566</prod_id>
    <prod_name>10-element cookware set KINGHOFF KH-4449</prod_name>
    <prod_desc>High quality stainless steel cookware set. Suitable for all cooktops.</prod_desc>
    <cat_path>Cookware/Sets</cat_path>
    <prod_shipping_time>4</prod_shipping_time>
    <prod_img>
      <img>https://kinghoff.online/images/kinghoff/0-1000/10-ELEMENTOWY-ZESTAW-GARNKOW-KINGHOFF-KH-4449_[854]_1200.jpg</img>
      <img>https://kinghoff.online/images/kinghoff/26000-27000/10-ELEMENTOWY-ZESTAW-GARNKOW-KINGHOFF-KH-4449_[26889]_1200.jpg</img>
      <img>https://kinghoff.online/images/kinghoff/26000-27000/10-ELEMENTOWY-ZESTAW-GARNKOW-KINGHOFF-KH-4449_[26890]_1200.jpg</img>
    </prod_img>
    <prod_price>50.00</prod_price>
    <prod_amount>12</prod_amount>
    <prod_ean>5908287244498</prod_ean>
  </item>
</products>
"""

# --- Išsaugome failus ---
with open("test_data/supplier1_test.xml", "w", encoding="utf-8") as f:
    f.write(supplier1_ext)

with open("test_data/supplier1_light.xml", "w", encoding="utf-8") as f:
    f.write(supplier1_light)

with open("test_data/supplier2_test.xml", "w", encoding="utf-8") as f:
    f.write(supplier2)

print("✅ Testiniai XML failai sukurti aplanke 'test_data/'")
