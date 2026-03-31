import pandas as pd
import numpy as np
import random

np.random.seed(42)
random.seed(42)

products = [
    "Paracetamol 500mg", "Amoxicillin 250mg", "Ibuprofen 400mg",
    "Omeprazole 20mg", "Metformin 500mg", "Atorvastatin 10mg",
    "Cetirizine 10mg", "Azithromycin 500mg", "Vitamin C 1000mg",
    "Calcium + D3", "Omega 3", "Zinc 50mg",
    "Cough Syrup 100ml", "Eye Drops 5ml", "Nasal Spray",
    "Insulin 100IU", "Aspirin 75mg", "Lisinopril 5mg",
    "Pantoprazole 40mg", "Doxycycline 100mg"
]

staff = ["Ahmed", "Sara", "Mohamed", "Fatma"]

rows = []
dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")

for date in dates:
    n_sales = random.randint(8, 25)
    for _ in range(n_sales):
        product = random.choice(products)
        units = random.randint(1, 10)
        price = round(random.uniform(15, 120), 2)
        hour = random.randint(9, 21)
        expiry_year = random.choice([2025, 2026, 2027])
        expiry_month = random.randint(1, 12)

        rows.append({
            "التاريخ": date,
            "اسم الصنف": product,
            "العبوات": units,
            "الأجمالى": round(units * price, 2),
            "الوقت": f"{hour:02d}:00",
            "المستخدم": random.choice(staff),
            "تاريخ الصلاحية": f"{expiry_year}/{expiry_month:02d}",
            "العملية": "مبيعات"
        })

    # بعض المرتجعات
    n_returns = random.randint(0, 2)
    for _ in range(n_returns):
        product = random.choice(products)
        units = random.randint(1, 3)
        price = round(random.uniform(15, 120), 2)
        rows.append({
            "التاريخ": date,
            "اسم الصنف": product,
            "العبوات": units,
            "الأجمالى": round(units * price, 2),
            "الوقت": f"{random.randint(9,21):02d}:00",
            "المستخدم": random.choice(staff),
            "تاريخ الصلاحية": f"2026/{random.randint(1,12):02d}",
            "العملية": "مرتجع مبيعات"
        })

df = pd.DataFrame(rows)
df.to_excel("/home/claude/pharmacy_project/sales.xlsx", sheet_name="ورقة1", index=False)
print(f"✅ Generated {len(df):,} rows")
print(df.head())
