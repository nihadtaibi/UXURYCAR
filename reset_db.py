import sqlite3

conn = sqlite3.connect('luxury_car.db')
cursor = conn.cursor()

# مسح جميع السيارات القديمة
cursor.execute('DELETE FROM voitures')

# إعادة تعيين الـ ID باش يبدأ من 1
cursor.execute('DELETE FROM sqlite_sequence WHERE name="voitures"')

conn.commit()
conn.close()

print("✅ تم مسح جميع السيارات القديمة بنجاح!")