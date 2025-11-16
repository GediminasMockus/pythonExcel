import os
import re
import time
import warnings
import xml.etree.ElementTree as ET
import pandas as pd
from deep_translator import GoogleTranslator
from tqdm import tqdm
import concurrent.futures

# ---------------- config ----------------
warnings.simplefilter(action='ignore', category=FutureWarning)
START_TIME = time.time()

TRANSLATE = False   # True = vykdome vertimą, False = tik originalūs tekstai
TRANSLATOR = GoogleTranslator(source='auto', target='lt')
SAVE_EVERY = 1000      # tarpinio failo intervalas
MIN_PRICE = 240
MAX_PRICE = None
MIN_QTY = 5
TMP_DIR = "tmp_partial"
os.makedirs(TMP_DIR, exist_ok=True)
MAX_WORKERS = 8

error_count = 0

# ---------------- helpers ----------------
def safe_float(s):
    try:
        return float(str(s).replace(",", "."))
    except:
        return 0.0

def safe_int(s):
    try:
        return int(float(str(s)))
    except:
        return 0

def translate_text(text):
    global error_count
    if not TRANSLATE or not text or not str(text).strip():
        return text
    try:
        return TRANSLATOR.translate(text)
    except Exception:
        error_count += 1
        return text

def translate_html_block(text):
    if not TRANSLATE or not text or not text.strip():
        return text
    try:
        def replace_tag(match):
            inner = match.group(1)
            tr = translate_text(inner)
            return match.group(0).replace(inner, tr)
        text = re.sub(r'<p.*?>(.*?)</p>', replace_tag, str(text), flags=re.DOTALL)
        text = re.sub(r'<span.*?>(.*?)</span>', replace_tag, text, flags=re.DOTALL)
        clean_text = re.sub(r'<.*?>', '', text)
        if clean_text.strip():
            return translate_text(clean_text)
        return text
    except Exception:
        return text

def batch_translate(texts):
    if not TRANSLATE:
        return texts
    results = [None]*len(texts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(translate_html_block, t): i for i, t in enumerate(texts)}
        for fut in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Vertimas"):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception:
                results[idx] = texts[idx]
    return results

def save_partial(df, supplier_tag, idx):
    fname = os.path.join(TMP_DIR, f"partial_{supplier_tag}_{idx}.xlsx")
    df.to_excel(fname, index=False)
    print(f"[INFO] Tarpinis failas: {fname}")

# ---------------- prefilter ----------------
def prefilter_supplier1(extended_file, light_file):
    tree_ext = ET.parse(extended_file).getroot()
    tree_light = ET.parse(light_file).getroot()
    light_dict = {o.get("i"): o for o in tree_light.iter("o")}
    products = list(tree_ext.iter("product"))
    filtered = []

    for p in tqdm(products, desc="Prefilter SP"):
        sku = p.findtext("id","").strip()
        o_elem = light_dict.get(sku)
        price_val = 0
        total_qty = 0
        if o_elem:
            for p_tag in o_elem.findall("p"):
                if p_tag.get("c") == "EUR" and p_tag.get("w"):
                    price_val = safe_float(p_tag.get("w"))
                    break
            for v in o_elem.findall("v"):
                total_qty += safe_int(v.text)
        if price_val < MIN_PRICE: continue
        if MAX_PRICE and price_val > MAX_PRICE: continue
        if total_qty < MIN_QTY: continue

        filtered.append({
            "element": p,
            "sku": sku,
            "raw_name": p.findtext("name",""),
            "raw_desc": p.findtext("description",""),
            "raw_cat": p.findtext("category",""),
            "delivery": p.findtext("delivery",""),
            "image": p.findtext("url",""),
            "o_elem": o_elem,
            "price": price_val,
            "qty": total_qty
        })
    print(f"[INFO] Tiekėjas1: filtruota {len(filtered)}/{len(products)}")
    return filtered

def prefilter_supplier2(file):
    tree = ET.parse(file).getroot()
    products = list(tree.iter("item"))
    filtered = []
    for p in tqdm(products, desc="Prefilter KH"):
        sku = p.findtext("prod_id","").strip()
        price_val = safe_float(p.findtext("prod_price","0"))
        qty_val = safe_int(p.findtext("prod_amount","0"))
        if price_val < MIN_PRICE: continue
        if MAX_PRICE and price_val > MAX_PRICE: continue
        if qty_val < MIN_QTY: continue

        filtered.append({
            "element": p,
            "sku": sku,
            "raw_name": p.findtext("prod_name",""),
            "raw_desc": p.findtext("prod_desc",""),
            "raw_cat": p.findtext("cat_path",""),
            "delivery": p.findtext("prod_shipping_time",""),
            "images": [img.text for img in p.findall(".//images/image")],
            "price": price_val,
            "qty": qty_val
        })
    print(f"[INFO] Tiekėjas2: filtruota {len(filtered)}/{len(products)}")
    return filtered

# ---------------- assemble ----------------
def process_supplier1(filtered_list, save_every=SAVE_EVERY):
    if not filtered_list:
        return pd.DataFrame(columns=[
            "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
            "Quantity","Variants","Parameters","AdditionalImages","Supplier"
        ])
    names = [it["raw_name"] for it in filtered_list]
    descs = [it["raw_desc"] for it in filtered_list]
    cats = [it["raw_cat"] for it in filtered_list]
    names_tr = batch_translate(names)
    descs_tr = batch_translate(descs)
    cats_tr = batch_translate(cats)

    rows=[]
    batch_rows=[]
    for idx,it in enumerate(filtered_list):
        p=it["element"]
        sku=it["sku"]
        name=names_tr[idx]
        desc=descs_tr[idx]
        cat=cats_tr[idx]
        delivery=it["delivery"]
        image=it["image"]
        price=it["price"]
        qty=it["qty"]

        params=[]
        for param in p.findall(".//parameters/parameter"):
            pname=param.get("name")
            pval=param.text
            if pname and pval:
                params.append(f"{translate_text(pname)}: {translate_text(pval)}")
        params_str="; ".join(params)

        variants=[]
        o_elem=it.get("o_elem")
        if o_elem:
            for item in p.findall(".//stock/item"):
                option=item.get("option")
                ean=item.get("ean") or ""
                val=(item.text or "").strip()
                qty_v=0
                for v in o_elem.findall("v"):
                    if v.get("i")==option:
                        qty_v = safe_int(v.text)
                        break
                if qty_v>0:
                    variants.append(f"{translate_text(val)} ({qty_v}) [{ean}]")
        variants_str=", ".join(variants)

        eans=[item.get("ean") for item in p.findall(".//stock/item") if item.get("ean")]
        barcode=", ".join(eans)

        imgs=[]
        for item in p.findall(".//stock/item"):
            url=item.findtext("url")
            if url:
                imgs.append(url)
        imgs=[image]+imgs if image else imgs
        main_image=imgs[0] if imgs else ""
        additional_images=", ".join(imgs[1:]) if len(imgs)>1 else ""

        row=[sku,name,desc,barcode,cat,delivery,main_image,price,qty,variants_str,params_str,additional_images]
        rows.append(row)
        batch_rows.append(row)

        if len(batch_rows)>=save_every or idx==len(filtered_list)-1:
            df_partial=pd.DataFrame(batch_rows,columns=[
                "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
                "Quantity","Variants","Parameters","AdditionalImages"
            ])
            save_partial(df_partial,"supplier1",idx+1)
            batch_rows=[]

    df=pd.DataFrame(rows,columns=[
        "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
        "Quantity","Variants","Parameters","AdditionalImages"
    ])
    df["Supplier"]="SP"
    return df

def process_supplier2(filtered_list, save_every=SAVE_EVERY):
    if not filtered_list:
        return pd.DataFrame(columns=[
            "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
            "Quantity","Variants","Parameters","AdditionalImages","Supplier"
        ])
    names=[it["raw_name"] for it in filtered_list]
    descs=[it["raw_desc"] for it in filtered_list]
    cats=[it["raw_cat"] for it in filtered_list]
    names_tr=batch_translate(names)
    descs_tr=batch_translate(descs)
    cats_tr=batch_translate(cats)

    rows=[]
    batch_rows=[]
    for idx,it in enumerate(filtered_list):
        p=it["element"]
        sku=it["sku"]
        name=names_tr[idx]
        desc=descs_tr[idx]
        cat=cats_tr[idx]
        delivery=it["delivery"]
        images=it.get("images",[])
        main_image=images[0] if images else ""
        additional_images=", ".join(images[1:]) if len(images)>1 else ""
        price=it["price"]
        qty=it["qty"]
        barcode=p.findtext("prod_ean","") or ""

        row=[sku,name,desc,barcode,cat,delivery,main_image,price,qty,"","",additional_images]
        rows.append(row)
        batch_rows.append(row)

        if len(batch_rows)>=save_every or idx==len(filtered_list)-1:
            df_partial=pd.DataFrame(batch_rows,columns=[
                "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
                "Quantity","Variants","Parameters","AdditionalImages"
            ])
            save_partial(df_partial,"supplier2",idx+1)
            batch_rows=[]

    df=pd.DataFrame(rows,columns=[
        "SKU","Name","Description","Barcode","Category","Delivery","Image","Price",
        "Quantity","Variants","Parameters","AdditionalImages"
    ])
    df["Supplier"]="KH"
    return df

# ---------------- main ----------------
def main():
    supplier1_ext="C:/Users/gedmo/Downloads/partner_b2b_full(1).xml"
    supplier1_light="C:/Users/gedmo/Downloads/partner-light(1).xml"
    supplier2_file="C:/Users/gedmo/Downloads/kh(1).xml"

    sp1_filtered=prefilter_supplier1(supplier1_ext,supplier1_light)
    sp2_filtered=prefilter_supplier2(supplier2_file)

    df1=process_supplier1(sp1_filtered)
    df2=process_supplier2(sp2_filtered)

    final_df=pd.concat([df1,df2],ignore_index=True) if not df1.empty or not df2.empty else pd.DataFrame()
    if final_df.empty:
        print("[WARN] Po filtracijos nėra produktų.")
        return

    final_df["BasePriceEUR"]=final_df["Price"].astype(float)
    def apply_markup(row):
        base=row["BasePriceEUR"]
        if base==0: return 0.0
        if base<5: m=200
        elif base<20: m=180
        elif base<50: m=150
        elif base<100: m=100
        else: m=80
        if row["Supplier"]=="KH": m+=5
        return round(base*(1+m/100))
    final_df["FinalPriceEUR"]=final_df.apply(apply_markup,axis=1)

    final_df=final_df.rename(columns={
        "SKU":"Prekės ID (SKU)",
        "Name":"Prekės pavadinimas",
        "Description":"Prekės aprašymas",
        "Barcode":"Barkodas",
        "Quantity":"Kiekis",
        "Delivery":"Pristatymo terminas (d.d.)",
        "Image":"Pagrindinė nuotrauka",
        "Variants":"Variantai",
        "Parameters":"Parametrai",
        "AdditionalImages":"Papildomos nuotraukos",
        "BasePriceEUR":"Pradinė kaina (EUR)",
        "FinalPriceEUR":"Galutinė kaina (EUR)",
        "Category":"Kategorija"
    })

    cols=[
        "Prekės ID (SKU)","Prekės pavadinimas","Prekės aprašymas","Barkodas",
        "Kiekis","Pristatymo terminas (d.d.)","Pradinė kaina (EUR)","Galutinė kaina (EUR)",
        "Variantai","Parametrai","Kategorija","Pagrindinė nuotrauka","Papildomos nuotraukos"
    ]
    final_df=final_df.reindex(columns=[c for c in cols if c in final_df.columns])
    final_df.to_excel("all_suppliers_translated.xlsx",index=False)
    print(f"\n✅ Galutinis Excel sukurtas: all_suppliers_translated.xlsx")
    print(f"⚠️ Vertimo klaidos: {error_count}")
    print(f"⏱ Viso laiko: {round(time.time()-START_TIME,2)} s")

if __name__=="__main__":
    main()
