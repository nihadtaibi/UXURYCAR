import sqlite3

conn = sqlite3.connect('luxury_car.db')
cursor = conn.cursor()

cursor.execute('''
    INSERT INTO voitures (nom, prix_jour, type, places, transmission, image, disponible)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', ('Dacia Sandero', 350, 'Citadine', 5, 'Manuelle', 'dacia_1.jpg', 1))

conn.commit()
conn.close()

print("✅ Voiture ajoutée avec succès!")