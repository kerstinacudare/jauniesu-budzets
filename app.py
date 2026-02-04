from flask import Flask, render_template, request, redirect, send_file
import sqlite3, os, pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS pasakumi (id INTEGER PRIMARY KEY, nosaukums TEXT, budzets REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS izdevumi (id INTEGER PRIMARY KEY, pasakums_id INTEGER, apraksts TEXT, summa REAL)")
    conn.commit()
    conn.close()

def import_from_excel():
    excel_path = os.path.join(BASE_DIR, "budzets_2026.xlsx")
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pasakumi")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path, sheet_name="Pasākumi")
        for _, row in df.iterrows():
            c.execute("INSERT INTO pasakumi (nosaukums, budzets) VALUES (?, ?)",
                      (row["Pasākums"], row["Budžets"]))
        conn.commit()
    conn.close()

init_db()
import_from_excel()

@app.route("/")
def index():
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT * FROM pasakumi")
    pasakumi = c.fetchall()

    data = []
    total_budget = total_spent = 0

    for p in pasakumi:
        c.execute("SELECT * FROM izdevumi WHERE pasakums_id=?", (p[0],))
        izdevumi = c.fetchall()
        spent = sum(i[3] for i in izdevumi)
        remaining = p[2] - spent
        total_budget += p[2]
        total_spent += spent
        data.append({"id":p[0],"nosaukums":p[1],"budzets":p[2],
                     "spent":spent,"remaining":remaining,"izdevumi":izdevumi})
    conn.close()
    return render_template("index.html", pasakumi=data,
                           total_budget=total_budget,
                           total_spent=total_spent,
                           total_remaining=total_budget-total_spent)

# PIEVIENOT JAUNU PASĀKUMU
@app.route("/add_event", methods=["POST"])
def add_event():
    conn = connect()
    conn.execute("INSERT INTO pasakumi (nosaukums, budzets) VALUES (?, ?)",
                 (request.form["nosaukums"], request.form["budzets"]))
    conn.commit()
    conn.close()
    return redirect("/")

# PALIELINĀT BUDŽETU
@app.route("/increase_budget", methods=["POST"])
def increase_budget():
    conn = connect()
    conn.execute("UPDATE pasakumi SET budzets = budzets + ? WHERE id=?",
                 (request.form["summa"], request.form["pasakums"]))
    conn.commit()
    conn.close()
    return redirect("/")

# PĀRDALĪT NAUDU
@app.route("/transfer", methods=["POST"])
def transfer():
    from_id = request.form["no"]
    to_id = request.form["uz"]
    summa = float(request.form["summa"])

    conn = connect()
    conn.execute("UPDATE pasakumi SET budzets = budzets - ? WHERE id=?", (summa, from_id))
    conn.execute("UPDATE pasakumi SET budzets = budzets + ? WHERE id=?", (summa, to_id))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if request.form["pasakums"] == "":
        return redirect("/")
    conn = connect()
    conn.execute("INSERT INTO izdevumi (pasakums_id, apraksts, summa) VALUES (?, ?, ?)",
                 (request.form["pasakums"], request.form["apraksts"], request.form["summa"]))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/delete_expense/<int:id>")
def delete_expense(id):
    conn = connect()
    conn.execute("DELETE FROM izdevumi WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/delete_event/<int:id>")
def delete_event(id):
    conn = connect()
    conn.execute("DELETE FROM izdevumi WHERE pasakums_id=?", (id,))
    conn.execute("DELETE FROM pasakumi WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/pdf/<int:id>")
def pdf(id):
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT nosaukums, budzets FROM pasakumi WHERE id=?", (id,))
    pasakums = c.fetchone()
    c.execute("SELECT apraksts, summa FROM izdevumi WHERE pasakums_id=?", (id,))
    izdevumi = c.fetchall()
    conn.close()

    file_path = os.path.join(BASE_DIR, f"atskaite_{id}.pdf")
    pdf = canvas.Canvas(file_path, pagesize=A4)
    y = 800
    pdf.drawString(50, y, f"Atskaite: {pasakums[0]}")
    y -= 30
    pdf.drawString(50, y, f"Budžets: {pasakums[1]} €")
    y -= 30
    for i in izdevumi:
        pdf.drawString(50, y, f"{i[0]} - {i[1]} €")
        y -= 20
    pdf.save()
    return send_file(file_path, as_attachment=True)
