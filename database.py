import sqlite3
from datetime import date

def init_db():
    conn = sqlite3.connect('luxury_car.db')
    cursor = conn.cursor()

    # 1. جدول السيارات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voitures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prix_jour REAL NOT NULL,
            type TEXT,
            places INTEGER,
            transmission TEXT,
            image TEXT,
            disponible INT GER DEFAULT 1
        )
    ''')

    # 2. جدول الحجوزات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voiture_id INTEGER,
            nom_client TEXT NOT NULL,
            telephone TEXT NOT NULL,
            date_debut TEXT NOT NULL,
            date_fin TEXT NOT NULL,
            lieu_livraison TEXT,
            prix_total REAL,
            statut TEXT DEFAULT 'en_attente',
            paye INTEGER DEFAULT 0,
            FOREIGN KEY (voiture_id) REFERENCES voitures (id)
        )
    ''')

    # 3. جدول الزبناء
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telephone TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Base de données créée avec succès!")


def get_disponibilite(voiture_id):
    conn = sqlite3.connect('luxury_car.db')
    cursor = conn.cursor()
    aujourd_hui = date.today().isoformat()
    
    cursor.execute('''
        SELECT date_fin FROM reservations
        WHERE voiture_id = ? AND statut = 'confirmé' AND date_fin >= ?
        ORDER BY date_fin DESC
        LIMIT 1
    ''', (voiture_id, aujourd_hui))
    
    resultat = cursor.fetchone()
    conn.close()
    
    if resultat:
        return {'disponible': False, 'date_disponible': resultat[0]}
    else:
        return {'disponible': True, 'date_disponible': None}


if __name__ == '__main__':
    init_db()