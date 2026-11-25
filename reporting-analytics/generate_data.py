"""Sample data banata hai: 12 mahine, 8 customers. Ek baar chalao."""
import random
import pandas as pd

random.seed(42)
customers = ["Ali Traders", "Noor Textiles", "Bismillah Store", "Khan Electronics",
             "Zara Fashion", "City Pharmacy", "Rehman Foods", "Super Mart"]
cities = ["Lahore", "Multan", "Layyah", "Karachi", "Islamabad", "Faisalabad", "Lahore", "Multan"]
months = pd.period_range("2025-12", "2026-11", freq="M")

cust_rows = []
for i, (c, city) in enumerate(zip(customers, cities), start=1):
    cust_rows.append({"id": i, "name": c, "city": city,
                      "created_at": str(months[min(i - 1, 11)].start_time.date())})
pd.DataFrame(cust_rows).to_csv("data/customers.csv", index=False)

sales = []
for idx, m in enumerate(months):
    for _ in range(random.randint(4, 7)):
        cid = random.randint(1, len(customers))
        if cust_rows[cid - 1]["created_at"] > str(m.end_time.date()):
            continue
        amount = random.randint(15, 60) * 1000 + idx * 800  # halka sa growth
        day = random.randint(1, 28)
        status = "paid" if random.random() > 0.2 else "unpaid"
        sales.append({"date": f"{m}-{day:02d}", "customer": customers[cid - 1],
                      "amount": amount, "status": status})
pd.DataFrame(sales).to_csv("data/sales.csv", index=False)

exp = []
for m in months:
    exp += [{"date": f"{m}-01", "category": "Rent", "amount": 40000},
            {"date": f"{m}-28", "category": "Salaries", "amount": random.randint(90, 110) * 1000},
            {"date": f"{m}-15", "category": "Marketing", "amount": random.randint(10, 30) * 1000},
            {"date": f"{m}-20", "category": "Utilities", "amount": random.randint(8, 15) * 1000}]
pd.DataFrame(exp).to_csv("data/expenses.csv", index=False)
print("Data ready: data/customers.csv, sales.csv, expenses.csv")
