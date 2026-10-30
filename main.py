Narijs.Y:
"""نظام إدارة مكتب عقارات - Tkinter + SQLite (بدون مكتبات خارجية).
Run: python main.py
The real_estate.db SQLite database is created next to this script.
"""
from future import annotations

import csv
import re
import sqlite3
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(file).resolve().parent
DB_FILE = APP_DIR / "real_estate.db"
CURRENCY = "د.ع"
SECTIONS = ("properties", "clients", "contracts", "payments")


class DataError(ValueError):
"""User-facing validation or business-rule error."""


def positive_int(value, label):
try:
n = int(str(value).strip())
except (ValueError, TypeError):
raise DataError(f"{label}: أدخل عدداً صحيحاً.") from None
if n <= 0:
raise DataError(f"{label}: يجب أن يكون أكبر من صفر.")
return n


def nonnegative_int(value, label):
try:
n = int(str(value).strip())
except (ValueError, TypeError):
raise DataError(f"{label}: أدخل عدداً صحيحاً.") from None
if n < 0:
raise DataError(f"{label}: لا يجوز أن يكون سالباً.")
return n


def parse_date(value, label="التاريخ", optional=False):
s = str(value or "").strip()
if not s and optional:
return ""
try:
return date.fromisoformat(s).isoformat()
except ValueError:
raise DataError(f"{label}: يجب استخدام الصيغة YYYY-MM-DD.") from None


def clean_required(value, label):
s = str(value or "").strip()
if not s:
raise DataError(f"{label}: هذا الحقل مطلوب.")
return s


class RealEstateDB:
def init(self, db_path=DB_FILE):
self.path = str(db_path)
self.con = sqlite3.connect(self.path)
self.con.row_factory = sqlite3.Row
self.con.execute("PRAGMA foreign_keys = ON")
self._init_schema()

def close(self):
self.con.close()

def _init_schema(self):
self.con.executescript("""
CREATE TABLE IF NOT EXISTS properties (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT NOT NULL,
location TEXT NOT NULL,
category TEXT NOT NULL,
offer_type TEXT NOT NULL CHECK (offer_type IN ('بيع','إيجار')),
area REAL NOT NULL CHECK (area > 0),
price INTEGER NOT NULL CHECK (price > 0),
rooms INTEGER NOT NULL DEFAULT 0 CHECK (rooms >= 0),
owner_name TEXT NOT NULL,
owner_phone TEXT NOT NULL DEFAULT '',
description TEXT NOT NULL DEFAULT '',
status TEXT NOT NULL DEFAULT 'متاح' CHECK (status IN ('متاح','مباع','مؤجر')),
created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS clients (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
phone TEXT NOT NULL,
email TEXT NOT NULL DEFAULT '',
client_type TEXT NOT NULL,
address TEXT NOT NULL DEFAULT '',
notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS contracts (
id INTEGER PRIMARY KEY AUTOINCREMENT,
property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
kind TEXT NOT NULL CHECK (kind IN ('بيع','إيجار')),
amount INTEGER NOT NULL CHECK (amount > 0),
contract_date TEXT NOT NULL,
end_date TEXT NOT NULL DEFAULT '',
status TEXT NOT NULL CHECK (status IN ('ساري','منتهي','ملغى')),
notes TEXT NOT NULL DEFAULT ''
);

Narijs.Y:
CREATE TABLE IF NOT EXISTS payments (
id INTEGER PRIMARY KEY AUTOINCREMENT,
contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE RESTRICT,
amount INTEGER NOT NULL CHECK (amount > 0),
payment_date TEXT NOT NULL,
method TEXT NOT NULL,
notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_contracts_property ON contracts(property_id);
CREATE INDEX IF NOT EXISTS ix_contracts_client ON contracts(client_id);
CREATE INDEX IF NOT EXISTS ix_payments_contract ON payments(contract_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_property_contract
ON contracts(property_id) WHERE status = 'ساري';
""")
self.con.commit()

def one(self, table, record_id):
if table not in SECTIONS:
raise DataError("نوع سجل غير معروف.")
return self.con.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()

def _validate_property(self, item):
try:
area = float(str(item.get("area", "")).strip())
except (ValueError, TypeError):
raise DataError("المساحة: أدخل قيمة رقمية صحيحة.") from None
if area <= 0:
raise DataError("المساحة: يجب أن تكون أكبر من صفر.")
kind = clean_required(item.get("offer_type"), "نوع العرض")
if kind not in ("بيع", "إيجار"):
raise DataError("نوع العرض غير صالح.")
return (
clean_required(item.get("title"), "عنوان العقار"),
clean_required(item.get("location"), "الموقع"),
clean_required(item.get("category"), "نوع العقار"), kind, area,
positive_int(item.get("price"), "السعر"),
nonnegative_int(item.get("rooms", 0), "عدد الغرف"),
clean_required(item.get("owner_name"), "اسم المالك"),
str(item.get("owner_phone", "")).strip(),
str(item.get("description", "")).strip(),
)

def save_property(self, item, record_id=None):
values = self._validate_property(item)
if record_id is None:
with self.con:
cur = self.con.execute("""INSERT INTO properties
(title,location,category,offer_type,area,price,rooms,owner_name,owner_phone,description)
VALUES (?,?,?,?,?,?,?,?,?,?)""", values)
return cur.lastrowid
current = self.one("properties", record_id)
if current is None:
raise DataError("العقار المطلوب غير موجود.")
if current["status"] != "متاح" and values[3] != current["offer_type"]:
raise DataError("لا يمكن تغيير نوع العرض وعليه عقد سارٍ.")
with self.con:
self.con.execute("""UPDATE properties SET
title=?,location=?,category=?,offer_type=?,area=?,price=?,rooms=?,
owner_name=?,owner_phone=?,description=? WHERE id=?""", (*values, record_id))
return record_id

def save_client(self, item, record_id=None):
values = (
clean_required(item.get("name"), "اسم العميل"),
clean_required(item.get("phone"), "رقم الهاتف"),
str(item.get("email", "")).strip(),
clean_required(item.get("client_type"), "تصنيف العميل"),
str(item.get("address", "")).strip(),
str(item.get("notes", "")).strip(),
)
if values[2] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values[2]):
raise DataError("البريد الإلكتروني غير صالح.")
with self.con:
if record_id is None:
cur = self.con.execute("""INSERT INTO clients
(name,phone,email,client_type,address,notes) VALUES (?,?,?,?,?,?)""", values)
return cur.lastrowid
else:
self.con.execute("""UPDATE clients SET name=?,phone=?,email=?,client_type=?,
address=?,notes=? WHERE id=?""", (*values, record_id))
return record_id

Narijs.Y:
def _sync_property(self, property_id):
active = self.con.execute("""SELECT kind FROM contracts
WHERE property_id=? AND status='ساري' LIMIT 1""", (property_id,)).fetchone()
status = "متاح" if not active else ("مباع" if active["kind"] == "بيع" else "مؤجر")
self.con.execute("UPDATE properties SET status=? WHERE id=?", (status, property_id))

def save_contract(self, item, record_id=None):
property_id = positive_int(item.get("property_id"), "العقار")
client_id = positive_int(item.get("client_id"), "العميل")
prop = self.one("properties", property_id)
client = self.one("clients", client_id)
if prop is None or client is None:
raise DataError("يجب اختيار عقار وعميل موجودين.")
kind = clean_required(item.get("kind"), "نوع العقد")
status = clean_required(item.get("status"), "حالة العقد")
if kind != prop["offer_type"]:
raise DataError("نوع العقد يجب أن يطابق نوع عرض العقار.")
if status not in ("ساري", "منتهي", "ملغى"):
raise DataError("حالة العقد غير صالحة.")
if kind == "بيع" and status == "منتهي":
raise DataError("حالة (منتهي) مخصصة لعقود الإيجار؛ استخدم (ملغى) لعقد البيع.")
amount = positive_int(item.get("amount"), "قيمة العقد")
contract_date = parse_date(item.get("contract_date"), "تاريخ العقد")
end_date = parse_date(item.get("end_date"), "تاريخ الانتهاء", optional=True)
if end_date and end_date < contract_date:
raise DataError("تاريخ الانتهاء لا يمكن أن يسبق تاريخ العقد.")
if status == "ساري":
other = self.con.execute("""SELECT id FROM contracts
WHERE property_id=? AND status='ساري' AND id<>?""",
(property_id, record_id if record_id is not None else -1)).fetchone()
if other:
raise DataError("هذا العقار مرتبط بعقد سارٍ آخر.")
if record_id is not None:
current = self.one("contracts", record_id)
if current is None:
raise DataError("العقد المطلوب غير موجود.")
paid = self.con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE contract_id=?",
(record_id,)).fetchone()[0]
if paid > amount:
raise DataError("قيمة العقد الجديدة أقل من مجموع الدفعات المسجلة.")
old_property_id = current["property_id"]
else:
old_property_id = None
values = (property_id, client_id, kind, amount, contract_date, end_date,
status, str(item.get("notes", "")).strip())
try:
with self.con:
if record_id is None:
cur = self.con.execute("""INSERT INTO contracts
(property_id,client_id,kind,amount,contract_date,end_date,status,notes)
VALUES (?,?,?,?,?,?,?,?)""", values)
else:
self.con.execute("""UPDATE contracts SET property_id=?,client_id=?,kind=?,amount=?,
contract_date=?,end_date=?,status=?,notes=? WHERE id=?""", (*values, record_id))
self._sync_property(property_id)
if old_property_id is not None and old_property_id != property_id:
self._sync_property(old_property_id)
return cur.lastrowid if record_id is None else record_id
except sqlite3.IntegrityError as exc:
raise DataError("يوجد تعارض في بيانات العقد أو عقد سارٍ لنفس العقار.") from exc

def save_payment(self, item, record_id=None):
contract_id = positive_int(item.get("contract_id"), "العقد")
contract = self.one("contracts", contract_id)
if contract is None:
raise DataError("العقد غير موجود.")

Narijs.Y:
if contract["status"] != "ساري":
raise DataError("يمكن تسجيل أو تعديل دفعات العقود السارية فقط.")
amount = positive_int(item.get("amount"), "قيمة الدفعة")
payment_date = parse_date(item.get("payment_date"), "تاريخ الدفعة")
method = clean_required(item.get("method"), "طريقة الدفع")
old = self.one("payments", record_id) if record_id is not None else None
if record_id is not None and old is None:
raise DataError("الدفعة غير موجودة.")
if old and old["contract_id"] != contract_id:
raise DataError("لا يمكن نقل دفعة موجودة إلى عقد آخر.")
total_other = self.con.execute("""SELECT COALESCE(SUM(amount),0)
FROM payments WHERE contract_id=? AND id<>?""",
(contract_id, record_id if record_id is not None else -1)).fetchone()[0]
if total_other + amount > contract["amount"]:
raise DataError(f"الدفعة تتجاوز المتبقي من قيمة العقد ({contract['amount'] - total_other:,} {CURRENCY}).")
values = (contract_id, amount, payment_date, method, str(item.get("notes", "")).strip())
with self.con:
if record_id is None:
self.con.execute("""INSERT INTO payments
(contract_id,amount,payment_date,method,notes) VALUES (?,?,?,?,?)""", values)
else:
self.con.execute("""UPDATE payments SET contract_id=?,amount=?,payment_date=?,
method=?,notes=? WHERE id=?""", (*values, record_id))

def delete(self, table, record_id):
if table not in SECTIONS:
raise DataError("نوع سجل غير معروف.")
record = self.one(table, record_id)
if record is None:
raise DataError("السجل غير موجود.")
if table == "contracts" and record["status"] == "ساري":
raise DataError("غيّر حالة العقد إلى (ملغى) أو (منتهي) قبل حذفه.")
try:
with self.con:
self.con.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
if table == "contracts":
self._sync_property(record["property_id"])
except sqlite3.IntegrityError as exc:
raise DataError("تعذّر الحذف: هذا السجل مرتبط بسجلات أخرى. احذف السجلات التابعة أولاً.") from exc

def rows(self, section, search="", status="الكل"):
if section == "properties":
query = """SELECT id,title,location,category,offer_type,area,price,rooms,status,owner_name
FROM properties WHERE (CAST(id AS TEXT) LIKE ? OR title LIKE ? OR location LIKE ? OR owner_name LIKE ?)"""
p = (f"%{search}%",) * 4
if status != "الكل":
query += " AND status=?"
p += (status,)
query += " ORDER BY id DESC"
elif section == "clients":
query = """SELECT id,name,phone,client_type,email,address
FROM clients WHERE name LIKE ? OR phone LIKE ? OR CAST(id AS TEXT) LIKE ? ORDER BY id DESC"""
p = (f"%{search}%",) * 3
elif section == "contracts":
query = """SELECT c.id,p.title AS property_title,cl.name AS client_name,c.kind,
c.amount,c.contract_date,c.end_date,c.status,
COALESCE((SELECT SUM(amount) FROM payments WHERE contract_id=c.id),0) AS paid,
(c.amount - COALESCE((SELECT SUM(amount) FROM payments WHERE contract_id=c.id),0)) AS remaining
FROM contracts c JOIN properties p ON p.id=c.property_id JOIN clients cl ON cl.id=c.client_id
WHERE p.title LIKE ? OR cl.name LIKE ? OR CAST(c.id AS TEXT) LIKE ?
ORDER BY c.id DESC"""
p = (f"%{search}%",) * 3
elif section == "payments":
query = """SELECT pay.id,pay.contract_id,p.title AS property_title,

Narijs.Y:
cl.name AS client_name,pay.amount,pay.payment_date,pay.method
FROM payments pay JOIN contracts c ON c.id=pay.contract_id
JOIN properties p ON p.id=c.property_id JOIN clients cl ON cl.id=c.client_id
WHERE p.title LIKE ? OR cl.name LIKE ? OR CAST(pay.contract_id AS TEXT) LIKE ?
ORDER BY pay.id DESC"""
p = (f"%{search}%",) * 3
else:
raise DataError("نوع قسم غير معروف.")
return self.con.execute(query, p).fetchall()

def stats(self):
scalar = lambda q: self.con.execute(q).fetchone()[0]
return {
"properties": scalar("SELECT COUNT(*) FROM properties"),
"available": scalar("SELECT COUNT(*) FROM properties WHERE status='متاح'"),
"sold": scalar("SELECT COUNT(*) FROM properties WHERE status='مباع'"),
"rented": scalar("SELECT COUNT(*) FROM properties WHERE status='مؤجر'"),
"clients": scalar("SELECT COUNT(*) FROM clients"),
"active_contracts": scalar("SELECT COUNT(*) FROM contracts WHERE status='ساري'"),
"contracts": scalar("SELECT COUNT(*) FROM contracts"),
"paid": scalar("SELECT COALESCE(SUM(amount),0) FROM payments"),
"contract_amount": scalar("SELECT COALESCE(SUM(amount),0) FROM contracts WHERE status='ساري'"),
}

def report_rows(self):
return self.con.execute("""SELECT p.category, COUNT(*) AS quantity,
SUM(CASE WHEN p.status='متاح' THEN 1 ELSE 0 END) AS available,
SUM(CASE WHEN p.status='مباع' THEN 1 ELSE 0 END) AS sold,
SUM(CASE WHEN p.status='مؤجر' THEN 1 ELSE 0 END) AS rented
FROM properties p GROUP BY p.category ORDER BY quantity DESC""").fetchall()

def selector_options(self, table, active_only=False):
if table == "properties":
return [(str(r["id"]), f"{r['id']} | {r['title']} | {r['offer_type']} | {r['status']}")
for r in self.con.execute("SELECT id,title,offer_type,status FROM properties ORDER BY id DESC")]
if table == "clients":
return [(str(r["id"]), f"{r['id']} | {r['name']} | {r['phone']}")
for r in self.con.execute("SELECT id,name,phone FROM clients ORDER BY id DESC")]
if table == "contracts":
where = "WHERE c.status='ساري'" if active_only else ""
query = f"""SELECT c.id,p.title,c.amount,c.status,
COALESCE(SUM(pay.amount),0) AS paid
FROM contracts c JOIN properties p ON p.id=c.property_id
LEFT JOIN payments pay ON pay.contract_id=c.id {where}
GROUP BY c.id ORDER BY c.id DESC"""
return [(str(r["id"]), f"{r['id']} | {r['title']} | المتبقي {r['amount']-r['paid']:,}")
for r in self.con.execute(query)]
return []

def seed_demo(self):
if any(self.con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in SECTIONS):
raise DataError("البيانات التجريبية تُضاف فقط إلى قاعدة بيانات فارغة.")
self.save_property(dict(title="شقة عائلية في حي الجامعة", location="الموصل - حي الجامعة",
category="شقة", offer_type="بيع", area="145", price="95000000", rooms="3",
owner_name="مالك تجريبي 1", owner_phone="", description="بيانات للعرض والتجربة فقط"))
rented_property_id = self.save_property(dict(title="منزل للإيجار", location="تلعفر - المركز",
category="منزل", offer_type="إيجار", area="200", price="650000", rooms="4",
owner_name="مالك تجريبي 2", owner_phone="", description="الإيجار الشهري ضمن المثال"))
self.save_property(dict(title="قطعة أرض سكنية", location="الموصل - الساحل الأيسر",
category="أرض", offer_type="بيع", area="250", price="120000000", rooms="0",

Narijs.Y:
owner_name="مالك تجريبي 3", owner_phone="", description="بيانات تجريبية"))
self.save_client(dict(name="عميل تجريبي أول", phone="07700000000", email="",
client_type="مشتري", address="نينوى", notes="للتجربة"))
renter_id = self.save_client(dict(name="عميل تجريبي ثانٍ", phone="07800000000", email="",
client_type="مستأجر", address="نينوى", notes="للتجربة"))
contract_id = self.save_contract(dict(property_id=str(rented_property_id), client_id=str(renter_id), kind="إيجار", amount="650000",
contract_date=date.today().isoformat(), end_date="", status="ساري", notes="عقد تجريبي"))
self.save_payment(dict(contract_id=str(contract_id), amount="200000", payment_date=date.today().isoformat(),
method="نقداً", notes="دفعة تجريبية"))

def backup(self, target_path):
dest = sqlite3.connect(str(target_path))
try:
self.con.backup(dest)
finally:
dest.close()


COLUMNS = {
"properties": [("id", "الرقم", 60), ("title", "العقار", 240), ("location", "الموقع", 170),
("category", "التصنيف", 90), ("offer_type", "العرض", 85), ("area", "م²", 75),
("price", "السعر (د.ع)", 135), ("rooms", "الغرف", 70),
("status", "الحالة", 90), ("owner_name", "المالك", 150)],
"clients": [("id", "الرقم", 70), ("name", "الاسم", 220), ("phone", "الهاتف", 160),
("client_type", "التصنيف", 100), ("email", "البريد", 200), ("address", "العنوان", 210)],
"contracts": [("id", "رقم العقد", 75), ("property_title", "العقار", 200),
("client_name", "العميل", 160), ("kind", "النوع", 70),
("amount", "القيمة (د.ع)", 125), ("contract_date", "تاريخ العقد", 115),
("end_date", "الانتهاء", 110), ("status", "الحالة", 80),
("paid", "المدفوع", 110), ("remaining", "المتبقي", 110)],
"payments": [("id", "رقم الدفعة", 95), ("contract_id", "رقم العقد", 100),
("property_title", "العقار", 230), ("client_name", "العميل", 180),
("amount", "المبلغ (د.ع)", 135), ("payment_date", "التاريخ", 125),
("method", "الطريقة", 110)],
}

FORM_FIELDS = {
"properties": [
("title", "اسم / عنوان العقار", "entry"), ("location", "الموقع", "entry"),
("category", "نوع العقار", ["شقة", "منزل", "أرض", "فيلا", "محل", "مكتب", "أخرى"]),
("offer_type", "نوع العرض", ["بيع", "إيجار"]),
("area", "المساحة بالمتر المربع", "entry"), ("price", "السعر بالدينار العراقي", "entry"),
("rooms", "عدد الغرف (صفر للأرض)", "entry"), ("owner_name", "اسم المالك", "entry"),
("owner_phone", "هاتف المالك", "entry"), ("description", "الوصف", "text")
],
"clients": [
("name", "الاسم الكامل", "entry"), ("phone", "رقم الهاتف", "entry"),
("email", "البريد الإلكتروني (اختياري)", "entry"),
("client_type", "تصنيف العميل", ["مشتري", "مستأجر", "مالك", "بائع", "أخرى"]),
("address", "العنوان", "entry"), ("notes", "ملاحظات", "text")
],
"contracts": [
("property_id", "العقار", "properties"), ("client_id", "العميل", "clients"),
("kind", "نوع العقد", ["بيع", "إيجار"]), ("amount", "قيمة العقد بالدينار", "entry"),
("contract_date", "تاريخ العقد YYYY-MM-DD", "entry"),
("end_date", "تاريخ الانتهاء (اختياري)", "entry"),
("status", "حالة العقد", ["ساري", "منتهي", "ملغى"]),
("notes", "ملاحظات", "text")
],
"payments": [
("contract_id", "العقد", "contracts"), ("amount", "المبلغ بالدينار", "entry"),
("payment_date", "تاريخ الدفع YYYY-MM-DD", "entry"),
("method", "طريقة الدفع", ["نقداً", "تحويل مصرفي", "بطاقة", "أخرى"]),
("notes", "ملاحظات", "text")
],
}

AR_NAMES = {"properties": "العقارات", "clients": "العملاء", "contracts": "العقود", "payments": "الدفعات"}

Narijs.Y:
class DataDialog(tk.Toplevel):
def init(self, parent, section, record_id=None):
super().init(parent)
self.parent = parent
self.db = parent.db
self.section = section
self.record_id = record_id
self.inputs = {}
self.selector_values = {}
self.title(("تعديل" if record_id else "إضافة") + " - " + AR_NAMES[section])
self.configure(bg="#F3F6FA")
self.geometry("1010x655" if section == "contracts" else ("840x580" if section == "properties" else "820x520"))
self.minsize(925, 635) if section == "contracts" else self.minsize(680, 440)
self.transient(parent)
self.grab_set()
record = self.db.one(section, record_id) if record_id else None
wrapper = ttk.Frame(self, padding=20)
wrapper.pack(fill="both", expand=True)
ttk.Label(wrapper, text=self.title(), style="DialogTitle.TLabel").pack(anchor="e", pady=(0, 10))
if section == "contracts":
self._build_contract_form(wrapper, record)
else:
self._build_regular_form(wrapper, record)
footer = ttk.Frame(wrapper)
footer.pack(fill="x", pady=(12, 0))
ttk.Button(footer, text="إلغاء", command=self.destroy).pack(side="left", padx=6)
ttk.Button(footer, text="حفظ البيانات", style="Accent.TButton", command=self.save).pack(side="right", padx=6)
ttk.Label(footer, text="* الخانات الأساسية مطلوبة، والتاريخ: YYYY-MM-DD.",
foreground="#66758C").pack(side="right", padx=10)
self.bind("<Escape>", lambda _e: self.destroy())
self.wait_visibility()
self.focus_force()

def _build_regular_form(self, wrapper, record):
section = self.section
form = ttk.Frame(wrapper)
form.pack(fill="both", expand=True)
form.columnconfigure(0, weight=1)
form.columnconfigure(1, weight=1)
for idx, (key, label, field_type) in enumerate(FORM_FIELDS[section]):
column = 1 - idx % 2 # start from right
row = idx // 2
cell = ttk.Frame(form, padding=(12, 6))
cell.grid(row=row, column=column, sticky="new")
ttk.Label(cell, text=label, anchor="e").pack(fill="x", pady=(0, 5))
val = str(record[key]) if record and record[key] is not None else ""
if field_type == "text":
widget = tk.Text(cell, height=3, font=("Tahoma", 10), wrap="word", relief="solid", bd=1)
widget.pack(fill="both", expand=True)
widget.insert("1.0", val)
elif field_type in ("properties", "clients", "contracts"):
options = self.db.selector_options(field_type, active_only=(field_type == "contracts"))
if record and field_type == "contracts" and not any(x[0] == val for x in options):
full = self.db.selector_options("contracts", active_only=False)
options += [x for x in full if x[0] == val]
mapping = {name: index for index, name in options}
reverse = {index: name for index, name in options}
self.selector_values[key] = mapping
widget = ttk.Combobox(cell, values=list(mapping.keys()), state="readonly", justify="right")
widget.pack(fill="x")
if val and val in reverse:
widget.set(reverse[val])
elif options:
widget.current(0)
elif isinstance(field_type, list):
widget = ttk.Combobox(cell, values=field_type, state="readonly", justify="right")
widget.pack(fill="x")
if val in field_type:
widget.set(val)
elif field_type:
widget.current(0)

Narijs.Y:
else:
widget = ttk.Entry(cell, justify="right")
widget.pack(fill="x")
if val:
widget.insert(0, val)
elif key in ("contract_date", "payment_date"):
widget.insert(0, date.today().isoformat())
elif key == "rooms":
widget.insert(0, "0")
self.inputs[key] = widget
def _build_contract_form(self, wrapper, record):
"""واجهة العقود فقط: أسماء للاختيار، وتفاصيل منفصلة للعرض دون تعديل بقية النوافذ."""
outer = ttk.Frame(wrapper)
outer.pack(fill="both", expand=True)
ttk.Label(outer, text="اختاري العقار والعميل من الاسم، ثم أدخلي تفاصيل العقد.",
foreground="#52657B").pack(anchor="e", pady=(0, 9))

parties = ttk.Frame(outer)
parties.pack(fill="x")
parties.columnconfigure(0, weight=1, uniform="party")
parties.columnconfigure(1, weight=1, uniform="party")

def make_party(table, key, column, heading, choice_label, specs):
card = ttk.LabelFrame(parties, text=heading, padding=(14, 10))
card.grid(row=0, column=column, sticky="nsew", padx=6)
ttk.Label(card, text=choice_label, anchor="e").pack(fill="x", pady=(0, 5))
if table == "properties":
rows = self.db.con.execute(
"SELECT id,title,location,offer_type,status FROM properties ORDER BY id DESC"
).fetchall()
name_field = "title"
other_field = "location"
else:
rows = self.db.con.execute(
"SELECT id,name,phone,client_type,address FROM clients ORDER BY id DESC"
).fetchall()
name_field = "name"
other_field = "phone"
counts = {}
for r in rows:
counts[r[name_field]] = counts.get(r[name_field], 0) + 1
mapping = {}
label_by_id = {}
detail_by_id = {}
for r in rows:
label = r[name_field]
if counts[label] > 1:
label += " — " + str(r[other_field] or "بدون تفاصيل")
if label in mapping:
label += f" — رقم {r['id']}"
mapping[label] = str(r["id"])
label_by_id[str(r["id"])] = label
detail_by_id[str(r["id"])] = r
self.selector_values[key] = mapping
picker = ttk.Combobox(card, values=list(mapping), state="readonly",
justify="right", font=("Tahoma", 11))
picker.pack(fill="x", ipady=3)
self.inputs[key] = picker

detail_frame = ttk.Frame(card)
detail_frame.pack(fill="x", pady=(8, 0))
detail_frame.columnconfigure(0, weight=1, uniform="details")
detail_frame.columnconfigure(1, weight=1, uniform="details")
display = {}
for index, (field, caption) in enumerate(specs):
row_num, col_num = divmod(index, 2)
col_num = 1 - col_num # يبدأ من اليمين
cell = ttk.Frame(detail_frame, padding=(5, 3))
cell.grid(row=row_num, column=col_num, sticky="ew")
ttk.Label(cell, text=caption, anchor="e").pack(side="right", padx=(8, 0))
variable = tk.StringVar(value="—")
tk.Label(cell, textvariable=variable, anchor="e", padx=7, pady=6,
bg="white", fg="#254052", bd=1, relief="solid",
font=("Tahoma", 10)).pack(side="right", fill="x", expand=True)
display[field] = variable

def on_selection(_event=None):
selected_id = mapping.get(picker.get())

Narijs.Y:
r = detail_by_id.get(selected_id)
for field, variable in display.items():
variable.set(str(r[field]) if r and r[field] not in (None, "") else "—")
if table == "properties" and r is not None and "kind" in self.inputs:
self.inputs["kind"].set(r["offer_type"])

picker.bind("<<ComboboxSelected>>", on_selection)
initial_id = str(record[key]) if record else ""
if initial_id in label_by_id:
picker.set(label_by_id[initial_id])
on_selection()
else:
picker.set("اختر العقار بالاسم" if table == "properties" else "اختر العميل بالاسم")
return on_selection

update_property = make_party(
"properties", "property_id", 1, "بيانات العقار", "اسم العقار",
[("id", "رقم العقار"), ("offer_type", "نوع العرض"),
("status", "حالة العقار"), ("location", "موقع العقار")]
)
make_party(
"clients", "client_id", 0, "بيانات العميل", "اسم العميل",
[("id", "رقم العميل"), ("phone", "رقم الهاتف"),
("client_type", "تصنيف العميل"), ("address", "العنوان")]
)

contract = ttk.LabelFrame(outer, text="بيانات العقد", padding=(16, 12))
contract.pack(fill="both", expand=True, padx=6, pady=(12, 0))
contract.columnconfigure(0, weight=1, uniform="contract")
contract.columnconfigure(1, weight=1, uniform="contract")

def add_field(key, caption, row, col, choices=None):
cell = ttk.Frame(contract, padding=(8, 4))
cell.grid(row=row, column=col, sticky="ew")
ttk.Label(cell, text=caption, anchor="e").pack(side="right", padx=(8, 0))
value = str(record[key]) if record and record[key] is not None else ""
if choices is not None:
widget = ttk.Combobox(cell, values=choices, state="readonly", justify="right",
font=("Tahoma", 10))
widget.set(value if value in choices else choices[0])
else:
widget = ttk.Entry(cell, justify="right", font=("Tahoma", 10))
if value:
widget.insert(0, value)
elif key == "contract_date":
widget.insert(0, date.today().isoformat())
widget.pack(side="right", fill="x", expand=True, ipady=2)
self.inputs[key] = widget

add_field("kind", "نوع العقد", 0, 1, ["بيع", "إيجار"])
add_field("amount", "قيمة العقد بالدينار العراقي", 0, 0)
add_field("contract_date", "تاريخ العقد YYYY-MM-DD", 1, 1)
add_field("end_date", "تاريخ الانتهاء (اختياري)", 1, 0)
add_field("status", "حالة العقد", 2, 1, ["ساري", "منتهي", "ملغى"])

note_cell = ttk.Frame(contract, padding=(8, 4))
note_cell.grid(row=3, column=0, columnspan=2, sticky="ew")
ttk.Label(note_cell, text="ملاحظات العقد (اختياري)", anchor="e").pack(fill="x", pady=(0, 4))
notes = tk.Text(note_cell, height=2, wrap="word", font=("Tahoma", 10), bd=1, relief="solid")
notes.pack(fill="x")
if record and record["notes"]:
notes.insert("1.0", record["notes"])
self.inputs["notes"] = notes
if not record:
# يطابق نوع العقد نوع العرض بمجرد اختيار عقار جديد.
update_property()

def save(self):
item = {}
for key, widget in self.inputs.items():
if isinstance(widget, tk.Text):
val = widget.get("1.0", "end-1c").strip()
else:
val = widget.get().strip()
if key in self.selector_values:
val = self.selector_values[key].get(val, "")
item[key] = val

Narijs.Y:
try:
handler = {"properties": self.db.save_property, "clients": self.db.save_client,
"contracts": self.db.save_contract, "payments": self.db.save_payment}[self.section]
handler(item, self.record_id)
except (DataError, sqlite3.IntegrityError) as exc:
messagebox.showerror("تعذر الحفظ", str(exc), parent=self)
return
self.parent.refresh_all()
self.destroy()


class RealEstateApp(tk.Tk):
def init(self, db_path=DB_FILE):
super().init()
self.db = RealEstateDB(db_path)
self.title("مكتب العقارات | نظام إدارة العقارات")
self.geometry("1220x780")
self.minsize(980, 625)
self.configure(bg="#EDF2F7")
self._styles()
self.search_vars = {}
self.tables = {}
self.rows_cache = {}
self.tabs = {}
self.status_var = tk.StringVar(value="الكل")
self._build()
self.refresh_all()
self.protocol("WM_DELETE_WINDOW", self._close)

def _styles(self):
style = ttk.Style(self)
if "clam" in style.theme_names():
style.theme_use("clam")
style.configure("TFrame", background="#F5F7FB")
style.configure("TLabel", background="#F5F7FB", foreground="#18283C", font=("Tahoma", 10))
style.configure("Title.TLabel", background="#15344F", foreground="white", font=("Tahoma", 19, "bold"))
style.configure("Sub.TLabel", background="#15344F", foreground="#D0E2EE", font=("Tahoma", 10))
style.configure("DialogTitle.TLabel", font=("Tahoma", 15, "bold"))
style.configure("TButton", font=("Tahoma", 10), padding=(11, 8))
style.configure("Accent.TButton", background="#087A73", foreground="white")
style.map("Accent.TButton", background=[("active", "#066A62")])
style.configure("Danger.TButton", background="#AB3845", foreground="white")
style.map("Danger.TButton", background=[("active", "#8F2B35")])
style.configure("Treeview", font=("Tahoma", 10), rowheight=30,
background="white", fieldbackground="white", foreground="#223147")
style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"),
background="#DEE8EF", foreground="#162E44", padding=6)
style.map("Treeview", background=[("selected", "#087A73")], foreground=[("selected", "white")])
style.configure("TNotebook", background="#EDF2F7", borderwidth=0)
style.configure("TNotebook.Tab", font=("Tahoma", 11, "bold"), padding=(20, 11))

def _build(self):
banner = tk.Frame(self, bg="#15344F", height=90)
banner.pack(fill="x")
banner.pack_propagate(False)
ttk.Label(banner, text="نظام إدارة مكتب العقارات", style="Title.TLabel").pack(anchor="e", padx=28, pady=(14, 0))
ttk.Label(banner, text="العقارات | العملاء | العقود | الدفعات | التقارير", style="Sub.TLabel").pack(
anchor="e", padx=30, pady=(2, 0))
self.nb = ttk.Notebook(self)
self.nb.pack(fill="both", expand=True, padx=14, pady=14)
self.tabs["dashboard"] = ttk.Frame(self.nb, padding=18)
self.nb.add(self.tabs["dashboard"], text="لوحة التحكم")
for section in SECTIONS:
self.tabs[section] = ttk.Frame(self.nb, padding=14)
self.nb.add(self.tabs[section], text=AR_NAMES[section])
self._build_table_tab(section)
self.tabs["reports"] = ttk.Frame(self.nb, padding=20)
self.nb.add(self.tabs["reports"], text="التقارير")
self._build_dashboard()
self._build_report()
bottom = tk.Frame(self, bg="#DCE5ED")
bottom.pack(fill="x")
tk.Label(bottom, text="Python · Tkinter · SQLite | تعمل قاعدة البيانات محلياً", bg="#DCE5ED",
fg="#42556B", font=("Tahoma", 9)).pack(side="right", padx=18, pady=4)

Narijs.Y:
def _build_table_tab(self, section):
frame = self.tabs[section]
toolbar = ttk.Frame(frame)
toolbar.pack(fill="x", pady=(0, 12))
ttk.Button(toolbar, text="+ إضافة", style="Accent.TButton",
command=lambda s=section: self.form(s)).pack(side="right", padx=3)
ttk.Button(toolbar, text="تعديل", command=lambda s=section: self.form(s, True)).pack(side="right", padx=3)
ttk.Button(toolbar, text="حذف", style="Danger.TButton",
command=lambda s=section: self.delete(s)).pack(side="right", padx=3)
ttk.Button(toolbar, text="تحديث", command=self.refresh_all).pack(side="right", padx=3)
ttk.Button(toolbar, text="تصدير CSV", command=lambda s=section: self.export_csv(s)).pack(side="right", padx=3)
if section == "properties":
ttk.Combobox(toolbar, textvariable=self.status_var, values=["الكل", "متاح", "مباع", "مؤجر"],
state="readonly", width=10, justify="right").pack(side="left", padx=6)
self.status_var.trace_add("write", lambda *_: self.refresh_table("properties"))
search_var = tk.StringVar()
self.search_vars[section] = search_var
search = ttk.Entry(toolbar, textvariable=search_var, width=27, justify="right")
search.pack(side="left", padx=6)
ttk.Label(toolbar, text="بحث:").pack(side="left", padx=(0, 6))
search_var.trace_add("write", lambda *_args, s=section: self.refresh_table(s))
table_frame = ttk.Frame(frame)
table_frame.pack(fill="both", expand=True)
col_def = COLUMNS[section]
columns = [x[0] for x in col_def]
tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
for key, label, width in col_def:
tree.heading(key, text=label)
tree.column(key, width=width, minwidth=60, anchor="center", stretch=False)
vscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
hscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
tree.grid(row=0, column=0, sticky="nsew")
vscroll.grid(row=0, column=1, sticky="ns")
hscroll.grid(row=1, column=0, sticky="ew")
table_frame.rowconfigure(0, weight=1)
table_frame.columnconfigure(0, weight=1)
tree.bind("<Double-1>", lambda _e, s=section: self.form(s, True))
self.tables[section] = tree
info = ttk.Frame(frame)
info.pack(fill="x", pady=(8, 0))
lbl = ttk.Label(info, text="", foreground="#607086")
lbl.pack(side="right")
setattr(self, "count_" + section, lbl)

def _build_dashboard(self):
f = self.tabs["dashboard"]
ttk.Label(f, text="ملخص المكتب", style="DialogTitle.TLabel").pack(anchor="e", pady=(0, 12))
tiles = ttk.Frame(f)
tiles.pack(fill="x")
self.kpi_labels = {}
metrics = [("properties", "إجمالي العقارات"), ("available", "عقارات متاحة"),
("clients", "العملاء"), ("active_contracts", "العقود السارية"),
("paid", "إجمالي الدفعات المسجلة")]
for i, (key, label) in enumerate(metrics):
tile = tk.Frame(tiles, bg="white", highlightbackground="#DCE3EB", highlightthickness=1)
tile.grid(row=0, column=i, sticky="nsew", padx=6, pady=7)
tk.Label(tile, text=label, bg="white", fg="#61758A", font=("Tahoma", 10)).pack(pady=(18, 4))
value_label = tk.Label(tile, text="0", bg="white", fg="#087A73", font=("Tahoma", 17, "bold"))
value_label.pack(pady=(0, 18))
self.kpi_labels[key] = value_label
tiles.columnconfigure(i, weight=1)
actions = ttk.Frame(f)

Narijs.Y:
actions.pack(fill="x", pady=(32, 10))
ttk.Button(actions, text="نسخة احتياطية من قاعدة البيانات", command=self.backup).pack(side="right", padx=5)
ttk.Button(actions, text="تحميل بيانات تجريبية", command=self.demo).pack(side="right", padx=5)
ttk.Button(actions, text="تحديث لوحة التحكم", command=self.refresh_all).pack(side="right", padx=5)
help_frame = tk.LabelFrame(f, text="طريقة الاستخدام السريعة", font=("Tahoma", 11, "bold"),
bg="#F5F7FB", fg="#172D44", padx=15, pady=13)
help_frame.pack(fill="both", expand=True, pady=(25, 0))
help_text = (
"١) أضف العقارات، ثم سجّل بيانات العملاء.\n\n"
"٢) أنشئ عقداً مرتبطاً بعقار وعميل، مع التأكد من مطابقة البيع أو الإيجار.\n\n"
"٣) سجّل الدفعات على العقود السارية فقط، ولا يمكن تجاوز إجمالي قيمة العقد.\n\n"
"٤) استخدم البحث والتصفية وتصدير CSV أو إنشاء نسخة احتياطية.\n\n"
"ملاحظة: حالة العقار تتغير تلقائياً عند تفعيل العقد أو إنهائه/إلغائه."
)
tk.Label(help_frame, text=help_text, bg="#F5F7FB", fg="#334A60", justify="right",
anchor="ne", font=("Tahoma", 11), wraplength=1040).pack(fill="both", anchor="e")

def _build_report(self):
f = self.tabs["reports"]
ttk.Label(f, text="التقارير والإحصائيات", style="DialogTitle.TLabel").pack(anchor="e")
ttk.Button(f, text="تحديث التقرير", command=self.refresh_reports).pack(anchor="e", pady=9)
self.report_text = tk.Text(f, wrap="word", font=("Tahoma", 12), bg="white",
fg="#18283C", bd=1, relief="solid", padx=25, pady=20)
self.report_text.pack(fill="both", expand=True)
self.report_text.tag_configure("rtl", justify="right", spacing3=13)
self.report_text.configure(state="disabled")

def selected_id(self, section):
selection = self.tables[section].selection()
if not selection:
messagebox.showwarning("لم يتم الاختيار", "اختر سجلاً من الجدول أولاً.", parent=self)
return None
return int(selection[0])

def form(self, section, edit=False):
record_id = self.selected_id(section) if edit else None
if edit and record_id is None:
return
try:
DataDialog(self, section, record_id)
except tk.TclError as exc:
messagebox.showerror("خطأ الواجهة", str(exc), parent=self)

def delete(self, section):
record_id = self.selected_id(section)
if record_id is None:
return
if not messagebox.askyesno("تأكيد الحذف", f"هل تريد حذف السجل رقم {record_id} من {AR_NAMES[section]}؟",
parent=self):
return
try:
self.db.delete(section, record_id)
except DataError as exc:
messagebox.showerror("تعذر الحذف", str(exc), parent=self)
return
self.refresh_all()

def refresh_table(self, section):
rows = self.db.rows(section, self.search_vars[section].get(),
self.status_var.get() if section == "properties" else "الكل")
self.rows_cache[section] = rows
tree = self.tables[section]
tree.delete(*tree.get_children())
for row in rows:
vals = []
for key, *_ in COLUMNS[section]:
value = row[key]
if key in ("price", "amount", "paid", "remaining") and value is not None:
value = f"{value:,}"
vals.append(value)
tree.insert("", "end", iid=str(row["id"]), values=vals)
getattr(self, "count_" + section).configure(text=f"عدد النتائج: {len(rows)}")

def refresh_all(self):
for section in SECTIONS:
self.refresh_table(section)
metrics = self.db.stats()
for key, label in self.kpi_labels.items():
value = f"{metrics[key]:,}" + (" د.ع" if key == "paid" else "")
label.configure(text=value)
self.refresh_reports()

Narijs.Y:
def refresh_reports(self):
metrics = self.db.stats()
types = self.db.report_rows()
sections = [
"تقرير موجز عن نشاط المكتب | " + datetime.now().strftime("%Y-%m-%d %H:%M"),
"", "إجمالي العقارات: {:,}".format(metrics["properties"]),
"العقارات المتاحة: {:,}".format(metrics["available"]),
"العقارات المباعة: {:,}".format(metrics["sold"]),
"العقارات المؤجرة: {:,}".format(metrics["rented"]),
"عدد العملاء: {:,}".format(metrics["clients"]),
"العقود السارية: {:,} / إجمالي العقود: {:,}".format(metrics["active_contracts"], metrics["contracts"]),
"القيمة الإجمالية للعقود السارية: {:,} د.ع".format(metrics["contract_amount"]),
"إجمالي الدفعات المسجلة لجميع العقود: {:,} د.ع".format(metrics["paid"]),
"", "توزيع العقارات حسب النوع:",
]
for r in types:
sections.append(f" • {r['category']}: {r['quantity']} إجمالاً | {r['available']} متاح | {r['sold']} مباع | {r['rented']} مؤجر")
if not types:
sections.append("لا توجد عقارات مسجلة حالياً.")
sections += ["", "ملاحظات:",
"• تُحتسب حالة العقار تلقائياً وفق العقد الساري.",
"• مجموع الدفعات يشمل الدفعات المرتبطة بعقود أُلغيت لاحقاً؛ يجب مراجعتها محاسبياً.",
"• هذا النظام مشروع تعليمي محلي، وليس بديلاً عن نظام محاسبة أو عقود قانونية معتمد."]
self.report_text.configure(state="normal")
self.report_text.delete("1.0", "end")
self.report_text.insert("1.0", "\n".join(sections), "rtl")
self.report_text.configure(state="disabled")

def export_csv(self, section):
path = filedialog.asksaveasfilename(parent=self, title="تصدير البيانات",
defaultextension=".csv", filetypes=[("CSV", "*.csv")],
initialfile=f"{section}_{date.today().isoformat()}.csv")
if not path:
return
try:
with open(path, "w", newline="", encoding="utf-8-sig") as f:
writer = csv.writer(f)
cols = COLUMNS[section]
writer.writerow([x[1] for x in cols])
for row in self.rows_cache.get(section, []):
writer.writerow([row[x[0]] for x in cols])
except OSError as exc:
messagebox.showerror("خطأ التصدير", str(exc), parent=self)
else:
messagebox.showinfo("نجاح", "تم تصدير نتائج الجدول الحالي إلى CSV.", parent=self)

def backup(self):
target = filedialog.asksaveasfilename(parent=self, title="حفظ نسخة احتياطية",
defaultextension=".db", filetypes=[("SQLite Database", "*.db")],
initialfile=f"real_estate_backup_{date.today().isoformat()}.db")
if not target:
return
if Path(target).resolve() == Path(self.db.path).resolve():
messagebox.showwarning("تنبيه", "اختر اسماً أو مساراً مختلفاً عن قاعدة البيانات الأصلية.", parent=self)
return
try:
self.db.backup(target)
messagebox.showinfo("نجاح", "تم إنشاء نسخة احتياطية سليمة من قاعدة البيانات.", parent=self)
except (OSError, sqlite3.Error) as exc:
messagebox.showerror("خطأ النسخ الاحتياطي", str(exc), parent=self)

def demo(self):
if not messagebox.askyesno("تأكيد", "هل تريد إضافة أمثلة تجريبية؟ يمكن ذلك فقط على قاعدة بيانات فارغة.", parent=self):
return
try:
self.db.seed_demo()
except DataError as exc:
messagebox.showerror("تعذرت العملية", str(exc), parent=self)
return
self.refresh_all()
messagebox.showinfo("تم", "أُضيفت 3 عقارات وعميلان وعقد ودفعة تجريبية.", parent=self)

def _close(self):
self.db.close()
self.destroy()


if name == "main":
RealEstateApp().mainloop()