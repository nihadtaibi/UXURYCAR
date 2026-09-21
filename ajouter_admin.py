import sqlite3

conn = sqlite3.connect('luxury_car.db')
cursor = conn.cursor()

cursor.execute('''
    INSERT INTO clients (nom, email, telephone, password, is_admin)
    VALUES (?, ?, ?, ?, 1)
''', ('Admin', 'admin@luxurycar.ma', '0600000000', 'Luxury2026!'))

conn.commit()
conn.close()

print("✅ Admin ajouté avec succès!")