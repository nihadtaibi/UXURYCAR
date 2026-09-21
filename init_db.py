import sqlite3

# الاتصال بقاعدة البيانات
conn = sqlite3.connect('luxury_car.db')
cursor = conn.cursor()

# مسح وإنشاء جدول السيارات
cursor.execute('DROP TABLE IF EXISTS voitures')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS voitures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        prix_jour REAL NOT NULL,
        type TEXT,
        places INTEGER,
        transmission TEXT,
        image TEXT,
        disponible INTEGER DEFAULT 1
    )
''')

# مسح وإنشاء جدول الحجوزات
cursor.execute('DROP TABLE IF EXISTS reservations')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voiture_id INTEGER,
        nom_client TEXT,
        telephone TEXT,
        date_debut TEXT,
        date_fin TEXT,
        lieu_livraison TEXT,
        prix_total REAL,
        statut TEXT DEFAULT 'en_attente',
        paye INTEGER DEFAULT 0,
        FOREIGN KEY(voiture_id) REFERENCES voitures(id)
    )
''')

# إضافة سيارات تجريبية
cars = [
    ('Dacia Logan', 400, 'Diesel', 5, 'Manuelle', 'dacia_1.jpg', 1),
    ('Renault Clio 5', 450, 'Diesel', 5, 'Manuelle', 'clio.jpg', 1),
    ('Volkswagen Golf 8', 700, 'Diesel', 5, 'Automatique', 'golf8.jpg', 1)
]
cursor.executemany('INSERT INTO voitures (nom, prix_jour, type, places, transmission, image, disponible) VALUES (?,?,?,?,?,?,?)', cars)

conn.commit()
conn.close()
print("قاعدة البيانات واجدة 100%")