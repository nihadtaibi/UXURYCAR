import os
import uuid
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, session, redirect, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'secret_uxurycar_key')

UPLOAD_FOLDER = os.path.join('static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
DB_NAME = 'luxury_car.db'

PHONE_1 = "+212 6 18 64 57 97"
PHONE_2 = "+212 7 54 29 64 40"
PHONE_3 = "+212 7 54 29 64 38"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# دالة مساعدة لاستعلامات قاعدة البيانات
# ==========================================
def query_db(query, args=(), fetchone=False, fetchall=False, commit=False):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        if commit:
            conn.commit()
            return cursor.lastrowid
        if fetchone:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()

# ==========================================
# إنشاء وتحديث الجداول
# ==========================================
def init_db():
    query_db('''CREATE TABLE IF NOT EXISTS voitures (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, prix_jour REAL, type TEXT,
        places INTEGER, transmission TEXT, image TEXT, disponible INTEGER DEFAULT 1)''', commit=True)
        
    query_db('''CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, voiture_id INTEGER, nom_client TEXT,
        telephone TEXT, date_debut TEXT, date_fin TEXT, lieu_livraison TEXT,
        prix_total REAL, remise REAL DEFAULT 0, type_charge TEXT DEFAULT '', montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'en_attente', paye INTEGER DEFAULT 0, num_contrat TEXT DEFAULT '',
        FOREIGN KEY (voiture_id) REFERENCES voitures (id))''', commit=True)

    query_db('''CREATE TABLE IF NOT EXISTS autres_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT, titre TEXT, montant REAL, mois TEXT, date_enregistrement TEXT)''', commit=True)

    for col in ["remise REAL DEFAULT 0", "type_charge TEXT DEFAULT ''", "montant_paye REAL DEFAULT 0", "num_contrat TEXT DEFAULT ''"]:
        try: query_db(f"ALTER TABLE reservations ADD COLUMN {col}", commit=True)
        except: pass
        
    query_db('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'admin')''', commit=True)
        
    try: query_db("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'", commit=True)
    except: pass
        
    # إضافة الحسابات الإفتراضية عند التشغيل لأول مرة فقط
    for uname, pwd, r in [('admin', 'admin123', 'admin'), ('shrik', 'shrik123', 'partner')]:
        user = query_db("SELECT id FROM users WHERE role = ?", (r,), fetchone=True)
        if not user:
            h_pass = generate_password_hash(pwd)
            query_db("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (uname, h_pass, r), commit=True)

init_db()

# ==========================================
# دالات جلب البيانات والسنة الشغالة
# ==========================================
def get_current_year():
    return session.get('selected_year', datetime.now().strftime('%Y'))

def get_voitures():
    return query_db('SELECT * FROM voitures ORDER BY id ASC', fetchall=True)

def get_voiture_by_id(voiture_id):
    return query_db('SELECT * FROM voitures WHERE id = ?', (voiture_id,), fetchone=True)

def get_date_disponibilite(voiture_id):
    row = query_db("SELECT date_fin FROM reservations WHERE voiture_id = ? AND statut = 'confirmé' ORDER BY date_fin DESC LIMIT 1", (voiture_id,), fetchone=True)
    if row and row[0]:
        try: return datetime.strptime(row[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        except: return row[0]
    return None

def is_logged_in(): return session.get('logged_in') == True
def is_full_admin(): return session.get('logged_in') == True and session.get('role') == 'admin'

# ==========================================
# التصميم وقائمة Sidebar (داخل 3 نقاط)
# ==========================================
STYLE = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9; color: #333; direction: ltr; }
    header { background-color: #111424; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); position: relative; z-index: 1000; }
    header h1 { font-size: 22px; font-weight: 900; letter-spacing: 2px; }
    header h1 span { color: #e94560; }
    .nav-links { display: flex; align-items: center; gap: 12px; }
    .nav-links a { color: #ddd; text-decoration: none; font-size: 13px; font-weight: 600; transition: 0.3s; padding: 8px 10px; border-radius: 6px; }
    .nav-links a:hover { color: white; background: rgba(255,255,255,0.1); }
    .header-year-select { background: #e94560; color: white; border: none; padding: 5px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; outline: none; }
    .header-year-select option { background: #111424; color: white; }
    .menu-dots-btn { background: none; border: none; color: white; font-size: 20px; cursor: pointer; padding: 5px 10px; border-radius: 6px; transition: 0.3s; }
    .menu-dots-btn:hover { background: rgba(255,255,255,0.1); color: #e94560; }
    .sidebar-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1001; display: none; opacity: 0; transition: opacity 0.3s ease; }
    .sidebar-overlay.active { display: block; opacity: 1; }
    .sidebar { position: fixed; top: 0; right: -300px; width: 280px; height: 100%; background: #111424; z-index: 1002; transition: right 0.3s ease; padding: 25px; box-shadow: -5px 0 15px rgba(0,0,0,0.2); display: flex; flex-direction: column; gap: 15px; }
    .sidebar.active { right: 0; }
    .sidebar-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; margin-bottom: 10px; }
    .sidebar-header h3 { color: white; font-size: 18px; margin: 0; }
    .close-sidebar { background: none; border: none; color: #aaa; font-size: 24px; cursor: pointer; }
    .close-sidebar:hover { color: white; }
    .sidebar-menu { display: flex; flex-direction: column; gap: 8px; }
    .sidebar-menu a { color: #ccc; text-decoration: none; padding: 12px 15px; border-radius: 8px; font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 12px; transition: 0.2s; }
    .sidebar-menu a:hover { background: #e94560; color: white; }
    .hero { background-color: #111424; color: white; text-align: center; padding: 60px 20px; }
    .hero h2 { font-size: 40px; font-weight: 900; letter-spacing: 3px; margin-bottom: 10px; }
    .hero p { font-size: 16px; color: #bbb; }
    .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
    .section-title { color: #111424; margin: 30px 0 15px; font-size: 22px; font-weight: 700; border-bottom: 3px solid #e94560; display: inline-block; padding-bottom: 5px; }
    .voitures-grid { display: flex; flex-wrap: wrap; gap: 25px; justify-content: center; }
    .voiture-card { background: white; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); width: 300px; text-align: center; overflow: hidden; transition: 0.3s; display: flex; flex-direction: column; justify-content: space-between; }
    .voiture-card:hover { transform: translateY(-5px); }
    .voiture-img { width: 100%; height: 180px; object-fit: cover; }
    .voiture-info { padding: 20px; flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between; }
    .prix { font-size: 20px; color: #e94560; font-weight: bold; margin: 8px 0; }
    .details { color: #777; font-size: 13px; margin-bottom: 15px; background: #f1f3f5; padding: 6px; border-radius: 5px; }
    .btn { background-color: #e94560; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; text-decoration: none; display: inline-block; font-weight: 600; text-align: center; }
    .btn:hover { background-color: #c73650; }
    .btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 4px; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; color: white; font-weight: 600; }
    .btn-warning { background-color: #ffc107; color: #212529; }
    .btn-warning:hover { background-color: #e0a800; }
    .form-container { background: white; max-width: 600px; margin: 40px auto; padding: 35px; border-radius: 12px; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }
    .success-box { background: white; max-width: 500px; margin: 60px auto; padding: 40px; border-radius: 12px; text-align: center; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }
    label { display: block; margin-top: 15px; margin-bottom: 5px; font-weight: 600; font-size: 14px; }
    input, select { width: 100%; padding: 11px; border: 1px solid #ced4da; border-radius: 6px; font-size: 14px; }
    .password-container { position: relative; width: 100%; }
    .password-container input { padding-right: 40px; }
    .toggle-password { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); cursor: pointer; user-select: none; font-size: 16px; opacity: 0.6; }
    .features-grid { display: flex; flex-wrap: wrap; gap: 20px; margin: 50px 0 30px; text-align: center; }
    .feature-card { flex: 1; min-width: 250px; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .feature-card h3 { color: #111424; margin: 10px 0 5px; font-size: 18px; }
    .feature-card p { color: #6c757d; font-size: 13px; }
    .contact-section { background: white; padding: 30px; border-radius: 12px; text-align: center; margin: 40px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .contact-section h3 { font-size: 20px; color: #111424; margin-bottom: 10px; }
    .contact-phones { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-top: 15px; }
    .phone-badge { background: #f1f3f5; padding: 10px 20px; border-radius: 30px; font-weight: bold; color: #111424; border: 1px solid #e2e8f0; }
    footer { background-color: #111424; color: white; padding: 35px 20px; text-align: center; margin-top: 50px; }
    .social-icons-static { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; pointer-events: none; }
    .social-icons-static div { color: #ffffff; font-size: 18px; width: 40px; height: 40px; background: rgba(255, 255, 255, 0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; }
    .dashboard-stats { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px; }
    .stat-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; flex: 1; min-width: 200px; border-top: 4px solid #e94560; }
    .stat-card h3 { font-size: 24px; color: #111424; margin-bottom: 5px; }
    .stat-card p { color: #6c757d; font-size: 13px; font-weight: 500; }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.04); margin-bottom: 30px; }
    th { background-color: #111424; color: white; padding: 14px; text-align: center; font-size: 13px; vertical-align: middle; }
    td { padding: 12px; border-bottom: 1px solid #dee2e6; font-size: 13px; vertical-align: middle; text-align: center; }
    tr:hover { background-color: #f8f9fa; }
    .role-badge { background: #6c5ce7; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; margin-left: 5px; }
    .year-badge { background: #e94560; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .month-navigator { display: flex; align-items: center; justify-content: center; gap: 20px; background: white; padding: 15px 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
    .nav-arrow { background: #111424; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; text-decoration: none; font-size: 18px; font-weight: bold; transition: 0.3s; }
    .nav-arrow:hover { background: #e94560; }
    .month-display { font-size: 20px; font-weight: bold; color: #111424; min-width: 180px; text-align: center; }
    .badge-top { background:#e94560; color:white; padding:2px 6px; border-radius:4px; font-size:11px; margin-left:5px;}
</style>

<script>
    function togglePasswordVisibility(inputId, eyeIconId) {
        const p = document.getElementById(inputId), e = document.getElementById(eyeIconId);
        p.type = p.type === 'password' ? 'text' : 'password';
        e.textContent = p.type === 'password' ? '👁️' : '👁️‍🗨️';
    }
    function openSidebar() {
        document.getElementById('sidebarOverlay').classList.add('active');
        document.getElementById('sidebarMenu').classList.add('active');
    }
    function closeSidebar() {
        document.getElementById('sidebarOverlay').classList.remove('active');
        document.getElementById('sidebarMenu').classList.remove('active');
    }
</script>
"""

def nav():
    if is_logged_in():
        role_label = "👑 Admin" if is_full_admin() else "👁️ Associé"
        active_year = get_current_year()
        
        # قائمة السنوات المتاحة للاختيار من الهيدر
        db_years = query_db("SELECT DISTINCT strftime('%Y', date_debut) FROM reservations WHERE date_debut IS NOT NULL UNION SELECT DISTINCT strftime('%Y', strftime('%Y-%m-%d', mois || '-01')) FROM autres_charges WHERE mois IS NOT NULL ORDER BY 1 DESC", fetchall=True)
        available_years = [y[0] for y in db_years if y[0]]
        default_years = [str(y) for y in range(2023, 2031)]
        all_years_set = sorted(list(set(available_years + default_years)), reverse=True)
        
        header_years_options = "".join([f"<option value='{yr}' {'selected' if yr == active_year else ''}>📅 {yr}</option>" for yr in all_years_set])
        
        sidebar = f"""
        <div id="sidebarOverlay" class="sidebar-overlay" onclick="closeSidebar()"></div>
        <div id="sidebarMenu" class="sidebar">
            <div class="sidebar-header">
                <h3>Options Menu</h3>
                <button class="close-sidebar" onclick="closeSidebar()">&times;</button>
            </div>
            <div class="sidebar-menu">
                <a href="/admin/historique">📜 Historiques</a>
                <a href="/admin/historique-general">📋 Disponibilités</a>
                <a href="/admin/voitures">🚗 Flotte De Véhicules</a>"""
        if is_full_admin():
            sidebar += """
                <a href="/admin/ajouter-voiture">➕ Ajouter Voiture</a>
                <a href="/admin/reservation-manuelle">📝 Client Direct (Magasin)</a>
                <a href="/admin/settings">⚙️ Paramètres</a>"""
        sidebar += """
                <a href="/deconnexion" style="margin-top:15px; background: rgba(220, 53, 69, 0.1); color:#dc3545;">🚪 Déconnexion</a>
            </div>
        </div>"""
        
        return f"""{sidebar}<header>
            <h1>UXURY<span>CAR</span></h1>
            <div class="nav-links">
                <a href="/admin">📊 Dashboard</a>
                <a href="/admin/statistiques">📈 Statistiques</a>
                <form action="/admin/change-year" method="POST" style="margin:0; display:inline-block;">
                    <input type="hidden" name="redirect_to" value="{request.path}">
                    <select name="selected_year" onchange="this.form.submit()" class="header-year-select">
                        {header_years_options}
                    </select>
                </form>
                <span class="role-badge">{role_label}</span>
                <button class="menu-dots-btn" onclick="openSidebar()"><i class="fas fa-ellipsis-v"></i></button>
            </div>
        </header>"""
    return """<header><h1>UXURY<span>CAR</span></h1><div class="nav-links">
        <a href="/">Accueil</a><a href="/connexion">Espace Pro / Admin</a>
    </div></header>"""

def footer():
    return f"""<footer>
        <p>&copy; 2026 UXURYCAR - Location de voitures de luxe au Maroc.</p>
        <p style='font-size:12px; color:#aaa; margin-top:5px;'>Service premium 24h/24 et 7j/7 dans tout le Maroc.</p>
        <div class="social-icons-static">
            <div><i class="fab fa-facebook-f"></i></div><div><i class="fab fa-instagram"></i></div>
            <div><i class="fab fa-snapchat"></i></div><div><i class="fab fa-tiktok"></i></div><div><i class="fab fa-whatsapp"></i></div>
        </div>
    </footer>"""

# ==========================================
# الصفحة الرئيسية
# ==========================================
@app.route('/')
def home():
    voitures = get_voitures()
    html = f"<html><head><title>UXURYCAR - Location de voitures</title>{STYLE}</head><body>{nav()}"
    html += """<div class="hero"><h2>UXURYCAR</h2><p>Location de voitures au Maroc — Simple, rapide & professionnel</p></div>
    <div class="container"><h2 class="section-title">Notre Flotte de Véhicules</h2><div class="voitures-grid">"""
    
    if not voitures:
        html += "<p style='width:100%; text-align:center; color:#777; padding:40px;'>Aucune voiture disponible pour le moment.</p>"

    for v in voitures:
        img_name = v[6] if len(v) > 6 and v[6] else 'kardian.jpg'
        if v[7] == 1:
            dispo_span = "<span style='color:#28a745; font-weight:bold;'>Disponible</span>"
            btn_html = f"<a href='/reserver/{v[0]}' class='btn'>Réserver</a>"
        else:
            date_dispo = get_date_disponibilite(v[0])
            dispo_text = f"Disponible à partir du : <b>{date_dispo}</b>" if date_dispo else "Réservée"
            dispo_span = f"<span style='color:#dc3545; font-weight:bold;'>Louée</span><br><small style='color:#6c757d; font-size:11px;'>{dispo_text}</small>"
            btn_html = "<button class='btn' style='background:#6c757d; cursor:not-allowed;' disabled>Non Disponible</button>"
        
        html += f"""<div class="voiture-card">
            <img src="/static/{img_name}" class="voiture-img" alt="{v[1]}" onerror="this.onerror=null; this.src='https://via.placeholder.com/300x180?text=UXURYCAR';">
            <div class="voiture-info">
                <div><h3>{v[1]}</h3><div class="prix">{v[2]} DH <span>/ jour</span></div><div class="details">{v[3]} | {v[4]} Places | {v[5]}</div></div>
                <div><p style='margin-bottom: 12px; font-size:13px;'>Statut: {dispo_span}</p>{btn_html}</div>
            </div>
        </div>"""
    
    return html + f"""</div>
    <div class="features-grid">
        <div class="feature-card"><div style="font-size:35px;">⏰</div><h3>Service 24h / 24</h3><p>Notre équipe reste à votre disposition 24h/24 et 7j/7.</p></div>
        <div class="feature-card"><div style="font-size:35px;">📍</div><h3>Livraison Partout</h3><p>Livraison à l'aéroport, hôtel ou domicile.</p></div>
        <div class="feature-card"><div style="font-size:35px;">🚘</div><h3>Meilleurs Tarifs</h3><p>Véhicules récents et parfaitement entretenus.</p></div>
    </div>
    <div class="contact-section">
        <h3>Pour plus d'informations, contactez-nous :</h3>
        <div class="contact-phones">
            <span class="phone-badge">📞 {PHONE_1}</span>
            <span class="phone-badge">📞 {PHONE_2}</span>
            <span class="phone-badge">📞 {PHONE_3}</span>
        </div>
    </div></div>{footer()}</body></html>"""

# ==========================================
# حجز زبون عادي
# ==========================================
@app.route('/reserver/<int:voiture_id>', methods=['GET', 'POST'])
def reserver(voiture_id):
    voiture = get_voiture_by_id(voiture_id)
    if not voiture: return redirect('/')
        
    if request.method == 'POST':
        try:
            d1, d2 = datetime.strptime(request.form['date_debut'], "%Y-%m-%d"), datetime.strptime(request.form['date_fin'], "%Y-%m-%d")
            jours = max((d2 - d1).days, 1)
        except: jours = 1
        prix_total = jours * voiture[2]

        query_db('''INSERT INTO reservations (voiture_id, nom_client, telephone, date_debut, date_fin, lieu_livraison, prix_total, remise, type_charge, montant_paye, statut, paye) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, '', 0, 'en_attente', 0)''', 
            (voiture_id, request.form['nom_client'], request.form['telephone'], request.form['date_debut'], request.form['date_fin'], request.form['lieu_livraison'], prix_total), commit=True)
        
        return f"<html><head>{STYLE}</head><body>{nav()}<div class='success-box'><h2>✅ Demande envoyée !</h2><p>Total estimé : {prix_total:.0f} DH</p><p>Votre demande est en cours de validation par notre équipe.</p><br><a href='/' class='btn'>Retour</a></div></body></html>"

    return f"<html><head>{STYLE}</head><body>{nav()}<div class='form-container'><h2>Réserver : {voiture[1]}</h2><form method='POST'><label>Nom Complet</label><input type='text' name='nom_client' required><label>Téléphone</label><input type='text' name='telephone' required><label>Date début</label><input type='date' name='date_debut' required><label>Date fin</label><input type='date' name='date_fin' required><label>Lieu de livraison</label><input type='text' name='lieu_livraison' required><br><br><button type='submit' class='btn' style='width:100%'>Confirmer la demande</button></form></div></body></html>"

# ==========================================
# Dashboard - لوحة التحكم
# ==========================================
@app.route('/admin')
def admin():
    if not is_logged_in(): return redirect('/connexion')
    
    selected_year = get_current_year()
    # جلب الشهر الحالي الحقيقي (مثلاً '09')
    current_m_only = datetime.now().strftime('%m')
    # تركيب الشهر مع السنة المختارة (مثلاً '2028-09')
    selected_month_filter = f"{selected_year}-{current_m_only}"
    
    # حساب مداخيل هذا الشهر بالنسبة للسنة المختارة فقط
    rev_m = query_db("SELECT SUM(montant_paye) FROM reservations WHERE date_debut LIKE ?", (f"{selected_month_filter}%",), fetchone=True)[0] or 0
    rev_tot = query_db("SELECT SUM(montant_paye) FROM reservations WHERE strftime('%Y', date_debut) = ?", (selected_year,), fetchone=True)[0] or 0

    reservations = query_db('''SELECT r.id, v.nom, r.nom_client, r.date_debut, r.date_fin, r.prix_total, r.remise, r.type_charge, r.montant_paye, r.num_contrat 
                               FROM reservations r JOIN voitures v ON r.voiture_id = v.id 
                               WHERE strftime('%Y', r.date_debut) = ? ORDER BY r.id DESC''', (selected_year,), fetchall=True)

    html = f"<html><head><title>Dashboard - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>"
    if not is_full_admin():
        html += "<div style='background:#fff3cd; color:#856404; padding:12px; border-radius:8px; margin-bottom:20px; font-size:13px;'>🔒 <b>Mode Lecture Seule :</b> Vous consultez le tableau de bord en tant qu'associé.</div>"

    html += f"""<h2 class='section-title'>📊 Tableau de bord financier ({selected_year})</h2>
        <div class='dashboard-stats'>
            <div class='stat-card' style='border-top-color:#28a745;'><h3>{rev_m:.0f} DH</h3><p>Revenu Encaissé (Ce Mois - {selected_year})</p></div>
            <div class='stat-card' style='border-top-color:#17a2b8;'><h3>{rev_tot:.0f} DH</h3><p>Total Encaissé ({selected_year})</p></div>
        </div>
        <h3 class='section-title'>📋 Liste des Réservations ({selected_year})</h3>
        
        <table>
            <thead>
                <tr style="background-color:#111424; color:white;">
                    <th rowspan="2">Voiture</th>
                    <th rowspan="2">N° Contrat</th>
                    <th rowspan="2">Dates</th>
                    <th rowspan="2">Payé</th>
                    <th rowspan="2">Reste</th>
                    <th colspan="2" style="background-color:#1c233a;">Les Charges</th>
                    <th rowspan="2">Total Net</th>
                    <th rowspan="2">Modifiée</th>
                </tr>
                <tr style="background-color:#252d47; color:white;">
                    <th>Type</th>
                    <th>Montant</th>
                </tr>
            </thead>
            <tbody>"""
            
    for r in reservations:
        p_tot, charge_m, charge_t, m_paye = r[5] or 0, r[6] or 0, r[7] or "-", r[8] or 0
        contrat_display = r[9] if (len(r) > 9 and r[9]) else f"#CTR-{r[0]:05d}"
        net_a_payer = p_tot - charge_m
        reste = net_a_payer - m_paye

        btn_modifiee = f"<a href='/admin/action/edit-paiement/{r[0]}' class='btn-sm btn-warning'>✏️ Modifiée</a>" if is_full_admin() else "<span style='color:#aaa;'>-</span>"

        html += f"""<tr>
            <td><b>{r[1]}</b><br><small style='color:#777;'>{r[2]}</small></td>
            <td><strong style='color:#e94560;'>{contrat_display}</strong></td>
            <td><small>Du {r[3]} au {r[4]}</small></td>
            <td style='color:#28a745; font-weight:bold;'>{m_paye:.0f} DH</td>
            <td style='color:#dc3545; font-weight:bold;'>{reste:.0f} DH</td>
            <td>{charge_t if charge_t else '-'}</td>
            <td style='font-weight:bold; color:#e67e22;'>{charge_m:.0f} DH</td>
            <td style='color:#17a2b8; font-weight:bold; font-size:14px;'>{m_paye:.0f} DH</td>
            <td>{btn_modifiee}</td>
        </tr>"""

    return html + "</tbody></table></div></body></html>"
    # ==========================================
# ✏️ التعديل وتحديث الدفعات والمصاريف
# ==========================================
@app.route('/admin/action/edit-paiement/<int:resa_id>', methods=['GET', 'POST'])
def edit_paiement(resa_id):
    if not is_full_admin(): return redirect('/admin')
    if request.method == 'POST':
        type_charge = request.form.get('type_charge', '')
        montant_charge = float(request.form.get('montant_charge', 0))
        m_paye = float(request.form.get('montant_paye', 0))
        num_contrat = request.form.get('num_contrat', '')
        
        p_total = query_db("SELECT prix_total FROM reservations WHERE id = ?", (resa_id,), fetchone=True)[0] or 0
        is_paid = 1 if (p_total - montant_charge - m_paye) <= 0 else 0
        
        query_db("UPDATE reservations SET type_charge = ?, remise = ?, montant_paye = ?, paye = ?, num_contrat = ? WHERE id = ?", 
                 (type_charge, montant_charge, m_paye, is_paid, num_contrat, resa_id), commit=True)
        return redirect('/admin')
        
    res = query_db('''SELECT r.id, v.nom, r.nom_client, r.prix_total, r.remise, r.type_charge, r.montant_paye, r.num_contrat 
                     FROM reservations r JOIN voitures v ON r.voiture_id = v.id WHERE r.id = ?''', (resa_id,), fetchone=True)
    if not res: return redirect('/admin')

    p_tot, rem, type_ch, paye = res[3] or 0, res[4] or 0, res[5] or '', res[6] or 0
    contrat_val = res[7] if res[7] else f"#CTR-{res[0]:05d}"

    return f"""<html><head>{STYLE}</head><body>{nav()}<div class="form-container">
        <h2>✏️ Modifier la réservation ({contrat_val})</h2>
        <p><b>Client :</b> {res[2]}</p>
        <p><b>Voiture :</b> {res[1]}</p>
        <p><b>Prix Total Initial :</b> <span style='color:#17a2b8; font-weight:bold;'>{p_tot:.0f} DH</span></p>
        <hr style='margin:15px 0;'>
        <form method="POST">
            <label>N° de Contrat (رقم العقد):</label>
            <input type="text" name="num_contrat" value="{contrat_val}" required style="font-weight:bold; color:#e94560;">

            <label>المبلغ المؤدى حتى الآن / Montant Payé (DH):</label>
            <input type="number" step="0.01" name="montant_paye" value="{paye}" required style="font-weight:bold; color:#28a745;">
            
            <fieldset style="border:1px dashed #e67e22; padding:15px; border-radius:8px; margin-top:20px;">
                <legend style="color:#e67e22; font-weight:bold;">🧾 Les Charges / المصاريف والتخفيضات</legend>
                <label>Type de Charge (النوع):</label>
                <input type="text" name="type_charge" value="{type_ch}" placeholder="مثال: Remise, Vidange, Lavage...">
                
                <label>Montant Charge (المبلغ DH):</label>
                <input type="number" step="0.01" name="montant_charge" value="{rem}" style="font-weight:bold; color:#e67e22;">
            </fieldset>

            <div style="background:#f8f9fa; padding:15px; margin-top:20px; border-radius:8px; border-left:4px solid #dc3545;">
                <strong>المتبقي للأداء / Reste à payer:</strong> 
                <span style="font-size:18px; color:#dc3545; font-weight:bold;">{(p_tot - rem - paye):.0f} DH</span>
            </div><br>
            <button type="submit" class="btn" style="width:100%; background-color:#28a745;">💾 Enregistrer les modifications</button>
            <a href="/admin" class="btn" style="width:100%; background-color:#6c757d; margin-top:10px;">Annuler</a>
        </form>
    </div></body></html>"""

# ==========================================
# 📜 Historique des Véhicules
# ==========================================
@app.route('/admin/historique')
def historique_liste():
    if not is_logged_in(): return redirect('/connexion')
    voitures = get_voitures()
    html = f"<html><head><title>Historiques - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>"
    html += "<h2 class='section-title'>📜 Historique des Véhicules</h2><p style='color:#6c757d; margin-bottom:25px;'>Sélectionnez un véhicule pour consulter son historique de location mensuel :</p><div class='voitures-grid'>"
    
    if not voitures: html += "<p style='width:100%; text-align:center; color:#777; padding:40px;'>Aucune voiture enregistrée.</p>"

    for v in voitures:
        img_name = v[6] if len(v) > 6 and v[6] else 'kardian.jpg'
        html += f"""<div class="voiture-card" style="cursor:pointer;" onclick="window.location.href='/admin/historique/voiture/{v[0]}'">
            <img src="/static/{img_name}" class="voiture-img" alt="{v[1]}" onerror="this.onerror=null; this.src='https://via.placeholder.com/300x180?text=UXURYCAR';">
            <div class="voiture-info">
                <div><h3>{v[1]}</h3><div class="details" style="margin-top:10px;">{v[3]} | {v[4]} Places | {v[5]}</div></div>
                <div><a href='/admin/historique/voiture/{v[0]}' class='btn' style='width:100%; margin-top:10px; background-color:#111424;'>📁 Voir Historique</a></div>
            </div>
        </div>"""
    return html + "</div></div></body></html>"

@app.route('/admin/historique/voiture/<int:voiture_id>')
def historique_detail_voiture(voiture_id):
    if not is_logged_in(): return redirect('/connexion')
    voiture = get_voiture_by_id(voiture_id)
    if not voiture: return redirect('/admin/historique')
        
    c_year = int(request.args.get('year', get_current_year()))
    c_month = int(request.args.get('month', datetime.now().month))
    
    p_month, p_year = (12, c_year - 1) if c_month - 1 < 1 else (c_month - 1, c_year)
    n_month, n_year = (1, c_year + 1) if c_month + 1 > 12 else (c_month + 1, c_year)
    
    reservations = query_db("SELECT id, date_debut, date_fin, num_contrat FROM reservations WHERE voiture_id = ? AND strftime('%Y-%m', date_debut) = ? ORDER BY id ASC", 
                            (voiture_id, f"{c_year}-{c_month:02d}"), fetchall=True)
    
    mois_noms = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    years_options = "".join([f"<option value='{y}' {'selected' if y == c_year else ''}>{y}</option>" for y in range(2023, 2031)])

    html = f"""<html><head><title>Historique {voiture[1]} - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; flex-wrap:wrap; gap:10px;">
            <a href="/admin/historique" class="btn" style="background:#6c757d;">⬅️ Retour à la liste</a>
            <h2 style="color:#111424; margin:0;">🚘 Historique : <b>{voiture[1]}</b></h2>
            <form method="GET" action="/admin/historique/voiture/{voiture_id}" style="margin:0; display:flex; align-items:center; gap:8px;">
                <input type="hidden" name="month" value="{c_month}">
                <label style="margin:0; font-weight:bold;">Année :</label>
                <select name="year" onchange="this.form.submit()" style="padding:6px 12px; font-weight:bold; border-radius:6px; background:white;">{years_options}</select>
            </form>
        </div>
        <div class="month-navigator">
            <a href="/admin/historique/voiture/{voiture_id}?month={p_month}&year={p_year}" class="nav-arrow">&lt;</a>
            <div class="month-display">📅 {mois_noms[c_month - 1]} {c_year}</div>
            <a href="/admin/historique/voiture/{voiture_id}?month={n_month}&year={n_year}" class="nav-arrow">&gt;</a>
        </div>
        <table><tr><th>Numéro de contrat</th><th>Durée (المدة)</th></tr>"""

    if not reservations:
        html += f"<tr><td colspan='2' style='text-align:center; padding:30px; color:#777;'>Aucune location enregistrée pour <b>{voiture[1]}</b> durant le mois de <b>{mois_noms[c_month - 1]} {c_year}</b>.</td></tr>"
    else:
        for r in reservations:
            c_code = r[3] if (len(r) > 3 and r[3]) else f"#CTR-{r[0]:05d}"
            try:
                jours = max((datetime.strptime(r[2], "%Y-%m-%d") - datetime.strptime(r[1], "%Y-%m-%d")).days, 1)
                duree = f"Du <b>{r[1]}</b> au <b>{r[2]}</b> ({jours} Jours)"
            except: duree = f"Du {r[1]} au {r[2]}"
            html += f"<tr><td><strong style='color:#e94560; font-size:14px;'>{c_code}</strong></td><td>{duree}</td></tr>"

    return html + "</table></div></body></html>"

# ==========================================
# 📄 Disponibilités
# ==========================================
@app.route('/admin/historique-general')
def disponibilites():
    if not is_logged_in(): return redirect('/connexion')
    selected_year = get_current_year()

    reservations = query_db('''SELECT v.nom, r.date_fin, r.statut 
                               FROM reservations r 
                               JOIN voitures v ON r.voiture_id = v.id 
                               WHERE strftime('%Y', r.date_debut) = ?
                               ORDER BY r.date_fin ASC''', (selected_year,), fetchall=True)

    today = datetime.now().date()
    data = []

    for r in reservations:
        try:
            date_retour = datetime.strptime(r[1], '%Y-%m-%d').date()
            jours_restants = (date_retour - today).days

            if jours_restants >= 0:
                data.append({
                    'vehicule': r[0],
                    'date_retour': r[1],
                    'jours_restants': jours_restants
                })
        except ValueError:
            continue

    data = sorted(data, key=lambda x: x['jours_restants'])

    html = f"<html><head><title>Disponibilités - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>"
    html += f"""<h2 class='section-title'>⏳ Disponibilité & Retours des Véhicules ({selected_year})</h2>
        <p style='color:#666; font-size:14px; margin-bottom:20px;'>متابعة موعد إرجاع السيارات (مرتبة حسب القرب)</p>

        <table>
            <thead>
                <tr style="background-color:#111424; color:white; height:45px;">
                    <th>Véhicule</th>
                    <th>Date de Retour</th>
                    <th>Jours Restants</th>
                </tr>
            </thead>
            <tbody>"""

    if not data:
        html += "<tr><td colspan='3' style='padding:15px;'>لا توجد سيارات مكرية حالياً.</td></tr>"

    for item in data:
        if item['jours_restants'] == 0:
            badge = "<span style='background:#dc3545; color:white; padding:4px 8px; border-radius:4px;'>Aujourd'hui (اليوم)</span>"
        elif item['jours_restants'] <= 2:
            badge = f"<span style='background:#fd7e14; color:white; padding:4px 8px; border-radius:4px;'>{item['jours_restants']} Jours</span>"
        else:
            badge = f"<span style='background:#28a745; color:white; padding:4px 8px; border-radius:4px;'>{item['jours_restants']} Jours</span>"

        html += f"""<tr style='height:40px;'>
            <td><b>{item['vehicule']}</b></td>
            <td><strong style='color:#007bff;'>{item['date_retour']}</strong></td>
            <td>{badge}</td>
        </tr>"""

    return html + "</tbody></table></div></body></html>"

# ==========================================
# المصاريف والإحصائيات
# ==========================================
@app.route('/admin/ajouter-autre-charge', methods=['POST'])
def ajouter_autre_charge():
    if not is_full_admin(): return redirect('/admin')
    titre, montant, mois = request.form.get('titre'), float(request.form.get('montant', 0)), request.form.get('mois')
    if titre and montant > 0 and mois:
        query_db("INSERT INTO autres_charges (titre, montant, mois, date_enregistrement) VALUES (?, ?, ?, ?)",
                 (titre, montant, mois, datetime.now().strftime('%Y-%m-%d')), commit=True)
    return redirect(f'/admin/statistiques?m={mois}')

# ==========================================
# 📊 Statistiques
# ==========================================
@app.route('/admin/statistiques')
def statistiques():
    if not is_logged_in(): return redirect('/connexion')
    selected_year = get_current_year()
    
    selected_month = request.args.get('m', f"{selected_year}-01")
    if not selected_month.startswith(selected_year):
        selected_month = f"{selected_year}-01"

    voitures = query_db('SELECT id, nom FROM voitures ORDER BY id ASC', fetchall=True)
    all_res = query_db('SELECT id, voiture_id, date_debut, date_fin, montant_paye, prix_total FROM reservations', fetchall=True)
    
    monthly_rev_by_car = {}
    monthly_rev_total = {}

    for r in all_res:
        r_id, v_id, d_debut, d_fin, m_paye, p_tot = r
        m_paye = m_paye or 0
        p_tot = p_tot or 1
        
        try:
            d1 = datetime.strptime(d_debut, '%Y-%m-%d')
            d2 = datetime.strptime(d_fin, '%Y-%m-%d')
            total_days = max((d2 - d1).days, 1)
        except:
            continue

        price_per_day = m_paye / total_days if m_paye > 0 else 0
        
        curr_d = d1
        seen_months_for_this_res = set()

        while curr_d < d2 or (curr_d == d1 and total_days == 1):
            m_str = curr_d.strftime('%Y-%m')
            
            if m_str not in monthly_rev_by_car:
                monthly_rev_by_car[m_str] = {}
            if v_id not in monthly_rev_by_car[m_str]:
                monthly_rev_by_car[m_str][v_id] = {'cnt': 0, 'rev': 0.0}

            if m_str not in monthly_rev_total:
                monthly_rev_total[m_str] = {'rev': 0.0, 'cnt': 0}

            monthly_rev_by_car[m_str][v_id]['rev'] += price_per_day
            monthly_rev_total[m_str]['rev'] += price_per_day

            if m_str not in seen_months_for_this_res:
                monthly_rev_by_car[m_str][v_id]['cnt'] += 1
                monthly_rev_total[m_str]['cnt'] += 1
                seen_months_for_this_res.add(m_str)

            curr_d += timedelta(days=1)
            if total_days == 1 and curr_d >= d2:
                break

    stats = []
    top_car_name = "Aucune"
    max_cnt = -1

    for v in voitures:
        v_id, v_nom = v[0], v[1]
        v_data = monthly_rev_by_car.get(selected_month, {}).get(v_id, {'cnt': 0, 'rev': 0.0})
        cnt_res = v_data['cnt']
        total_rev = v_data['rev']

        stats.append((v_id, v_nom, cnt_res, total_rev))
        if cnt_res > max_cnt and cnt_res > 0:
            max_cnt = cnt_res
            top_car_name = v_nom

    charges_months = query_db("SELECT DISTINCT mois FROM autres_charges WHERE mois LIKE ?", (f"{selected_year}%",), fetchall=True)
    all_months = sorted(list(set(list(monthly_rev_total.keys()) + [c[0] for c in charges_months if c[0]])), reverse=True)
    all_months = [m for m in all_months if m.startswith(selected_year)]

    if not all_months:
        all_months = [f"{selected_year}-01"]
    if selected_month not in all_months:
        all_months.insert(0, selected_month)

    monthly_data = []
    best_m, best_rev, low_m, low_rev = "Aucun", -999999, "Aucun", float('inf')

    for m_str in all_months:
        m_rev = monthly_rev_total.get(m_str, {}).get('rev', 0.0)
        m_cnt = monthly_rev_total.get(m_str, {}).get('cnt', 0)
        
        ch_row = query_db("SELECT SUM(montant) FROM autres_charges WHERE mois = ?", (m_str,), fetchone=True)
        m_ch = ch_row[0] or 0.0

        p_net = m_rev - m_ch
        monthly_data.append((m_str, m_rev, m_cnt, m_ch))

        if p_net > best_rev: best_rev, best_m = p_net, m_str
        if p_net < low_rev: low_rev, low_m = p_net, m_str

    if low_rev == float('inf'): low_rev = 0
    if best_rev == -999999: best_rev = 0

    month_options = "".join([f"<option value='{m}' {'selected' if m == selected_month else ''}>📅 {m}</option>" for m in all_months])

    html = f"""<html><head><title>Statistiques - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>
        <h2 class='section-title'>📈 Statistiques Financières ({selected_year})</h2>
        <div class='dashboard-stats'>
            <div class='stat-card' style='border-top-color:#28a745;'><h3>{best_m} ({best_rev:.0f} DH)</h3><p>🔥 Meilleur Profit Net ({selected_year})</p></div>
            <div class='stat-card' style='border-top-color:#dc3545;'><h3>{low_m} ({low_rev:.0f} DH)</h3><p>📉 Moins Bon Profit Net ({selected_year})</p></div>
            <div class='stat-card' style='border-top-color:#e94560;'><h3>{top_car_name}</h3><p>🚘 Top Voiture ({selected_month})</p></div>
        </div>
        <div style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
            <div><h3 style="margin:0; color:#111424;">📊 Performance par Véhicule</h3><p style="color:#777; font-size:13px; margin-top:3px;">Mois sélectionné: <b>{selected_month}</b></p></div>
            <form method="GET" action="/admin/statistiques" style="margin:0; display:flex; align-items:center; gap:10px;">
                <label style="margin:0; font-weight:bold;">Changer le mois :</label>
                <select name="m" onchange="this.form.submit()" style="padding: 8px 15px; border-radius: 6px; font-weight: bold; background: #f8f9fa;">{month_options}</select>
            </form>
        </div>
        <table><tr><th>N°</th><th>Modèle Voiture</th><th>Réservations ({selected_month})</th><th>Total Encaissé ({selected_month})</th></tr>"""

    for index, row in enumerate(stats, 1):
        v_id, v_nom, cnt_res, total_rev = row
        is_top = " <span class='badge badge-top'>Top 🏆</span>" if v_nom == top_car_name and cnt_res > 0 else ""
        html += f"<tr><td><strong>#{index}</strong></td><td><strong>{v_nom}</strong> {is_top}</td><td><strong>{cnt_res} fois</strong></td><td style='color:#28a745; font-weight:bold; font-size:15px;'>+{total_rev:.0f} DH</td></tr>"

    html += f"""</table><h3 class='section-title' style='margin-top:40px;'>📅 Historique Mensuel Global & Charges ({selected_year})</h3>
        <table><tr><th>Mois (الشهر)</th><th>Réservations</th><th>Recettes (المداخيل)</th><th>Autres Charges (الضرائب والرواتب)</th><th>Profit Net Réel (الربح الصافي)</th></tr>"""

    for m_str, m_rev, m_cnt, m_ch in monthly_data:
        p_net = m_rev - m_ch
        html += f"<tr><td><strong>📅 {m_str}</strong></td><td><b>{m_cnt} Réservations</b></td><td style='color:#28a745; font-weight:bold; font-size:14px;'>+{m_rev:.0f} DH</td><td style='color:#e67e22; font-weight:bold; font-size:14px;'>-{m_ch:.0f} DH</td><td style='color:{'#28a745' if p_net >= 0 else '#dc3545'}; font-weight:bold; font-size:16px;'>{p_net:.0f} DH</td></tr>"

    html += "</table>"
    if is_full_admin():
        html += f"""<div style="background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-top: 30px;">
            <h3 style="color:#111424; margin-bottom: 10px;">💸 Ajouter une Autre Charge (Salaires, Impôts, etc.)</h3>
            <form method="POST" action="/admin/ajouter-autre-charge" style="display:flex; gap:15px; flex-wrap:wrap; align-items:flex-end;">
                <div style="flex:2; min-width:200px;"><label style="margin-top:0;">Titre de la charge</label><input type="text" name="titre" placeholder="Ex: Salaires, Vignette, Impôts..." required></div>
                <div style="flex:1; min-width:150px;"><label style="margin-top:0;">Montant (DH)</label><input type="number" step="0.01" name="montant" placeholder="5000" required></div>
                <div style="flex:1; min-width:150px;"><label style="margin-top:0;">Mois Concerné</label><input type="month" name="mois" value="{selected_month}" required></div>
                <div><button type="submit" class="btn" style="background:#e94560; padding:12px 25px;">➕ Enregistrer</button></div>
            </form>
        </div>"""

    return html + "</div></body></html>"

# ==========================================
# 📝 Client Direct (Magasin)
# ==========================================
@app.route('/admin/reservation-manuelle', methods=['GET', 'POST'])
def reservation_manuelle():
    if not is_logged_in(): return redirect('/connexion')
    if not is_full_admin(): return "Accès refusé", 403

    if request.method == 'POST':
        voiture_id = request.form.get('voiture_id')
        nom_client = request.form.get('nom_client')
        num_contrat = request.form.get('num_contrat', '')
        telephone = ""
        date_debut = request.form.get('date_debut')
        date_fin = request.form.get('date_fin')
        acompte = float(request.form.get('acompte') or 0)
        
        type_charge = request.form.get('type_charge', '')
        montant_charge = float(request.form.get('montant_charge') or 0)

        voiture = query_db("SELECT prix_jour FROM voitures WHERE id = ?", (voiture_id,), fetchone=True)
        prix_jour = voiture[0] if voiture else 0
        
        try:
            d1 = datetime.strptime(date_debut, '%Y-%m-%d')
            d2 = datetime.strptime(date_fin, '%Y-%m-%d')
            jours = max((d2 - d1).days, 1)
        except:
            jours = 1
            
        prix_total = (jours * prix_jour) if prix_jour > 0 else (acompte + montant_charge)

        query_db('''INSERT INTO reservations 
                      (voiture_id, nom_client, telephone, date_debut, date_fin, prix_total, remise, type_charge, montant_paye, statut, paye, num_contrat)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmé', ?, ?)''',
                   (voiture_id, nom_client, telephone, date_debut, date_fin, prix_total, montant_charge, type_charge, acompte, 1 if acompte >= (prix_total - montant_charge) else 0, num_contrat), commit=True)

        query_db("UPDATE voitures SET disponible = 0 WHERE id = ?", (voiture_id,), commit=True)
        return redirect('/admin')

    voitures = query_db("SELECT id, nom, prix_jour FROM voitures ORDER BY id ASC", fetchall=True)

    html = f"<html><head><title>Client Direct - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container'>"
    html += f"""
    <div style='max-width: 600px; margin: 30px auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
        <h2 style='text-align:center; color:#1a252f; margin-bottom:20px;'>🚗 Client Direct (Magasin)</h2>
        
        <form method='POST'>
            <div style='margin-bottom:15px;'>
                <label><b>N° de Contrat (رقم العقد) :</b></label>
                <input type='text' name='num_contrat' placeholder='مثال: CTR-2026-001' required style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc; font-weight:bold; color:#e94560;'>
            </div>

            <div style='margin-bottom:15px;'>
                <label><b>Choisir la Voiture :</b></label>
                <select name='voiture_id' required style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc;'>
                    {"".join([f"<option value='{v[0]}'>{v[1]} ({v[2]} DH/j)</option>" for v in voitures])}
                </select>
            </div>

            <div style='margin-bottom:15px;'>
                <label><b>Nom Complet du Client :</b></label>
                <input type='text' name='nom_client' required style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc;'>
            </div>

            <div style='display:flex; gap:10px; margin-bottom:15px;'>
                <div style='flex:1;'>
                    <label><b>Date de prise :</b></label>
                    <input type='date' name='date_debut' required style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc;'>
                </div>
                <div style='flex:1;'>
                    <label><b>Date de retour :</b></label>
                    <input type='date' name='date_fin' required style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc;'>
                </div>
            </div>

            <div style='margin-bottom:15px;'>
                <label><b>Montant Payé (Advance / Avance DH) :</b></label>
                <input type='number' name='acompte' value='0' style='width:100%; padding:10px; border-radius:6px; border:1px solid #ccc; font-weight:bold; color:#28a745;'>
            </div>

            <fieldset style='border:1px dashed #e67e22; padding:15px; border-radius:8px; margin-bottom:20px;'>
                <legend style='color:#e67e22; font-weight:bold;'>🧾 Les Charges (المصاريف / التخفيض)</legend>
                
                <div style='margin-bottom:10px;'>
                    <label><b>Type de Charge (النوع) :</b></label>
                    <input type='text' name='type_charge' placeholder='مثال: Remise, Vidange, Lavage...' style='width:100%; padding:8px; border-radius:6px; border:1px solid #ccc;'>
                </div>

                <div>
                    <label><b>Montant Charge (الثمن DH) :</b></label>
                    <input type='number' name='montant_charge' value='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid #ccc; font-weight:bold; color:#e67e22;'>
                </div>
            </fieldset>

            <button type='submit' style='width:100%; background:#28a745; color:white; padding:12px; border:none; border-radius:6px; font-weight:bold; font-size:16px; cursor:pointer;'>
                ✅ Valider & Enregistrer la réservation
            </button>
        </form>
    </div>
    </body></html>
    """
    return html

# ==========================================
# إدارة السيارات والروابط
# ==========================================
@app.route('/admin/voitures')
def admin_voitures():
    if not is_logged_in(): return redirect('/connexion')
    html = f"<html><head>{STYLE}</head><body>{nav()}<div class='container'><h2 class='section-title'>🚗 Flotte de Véhicules</h2><table><tr><th>N°</th><th>Modèle</th><th>Prix / Jour</th>{'<th>Actions</th>' if is_full_admin() else ''}</tr>"
    for index, v in enumerate(get_voitures(), 1):
        action_td = f"<td><a href='/admin/voitures/modifier/{v[0]}' class='btn-sm btn-warning'>✏️ Modifier</a> <a href='/admin/voitures/supprimer/{v[0]}' class='btn-sm btn-danger' onclick=\"return confirm('Supprimer ?')\">🗑️ Supprimer</a></td>" if is_full_admin() else ""
        html += f"<tr><td><strong>#{index}</strong></td><td><strong>{v[1]}</strong></td><td>{v[2]} DH/j</td>{action_td}</tr>"
    return html + "</table></div></body></html>"

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    msg = ""
    if request.method == 'POST':
        account = query_db("SELECT * FROM users WHERE username = ?", (request.form['username'],), fetchone=True)
        if account and check_password_hash(account[2], request.form['password']):
            session['logged_in'], session['username'], session['role'] = True, account[1], account[3]
            return redirect('/admin')
        msg = "❌ Nom d'utilisateur ou mot de passe incorrect !"
            
    return f"""<html><head>{STYLE}</head><body>{nav()}<div class='form-container'>
        <h2>Connexion Espace Pro</h2><p style='color:red; text-align:center; font-weight:bold;'>{msg}</p>
        <form method='POST'>
            <label>Utilisateur:</label><input type='text' name='username' required placeholder="admin ou shrik">
            <label>Mot de passe:</label>
            <div class="password-container">
                <input type='password' id='loginPassword' name='password' required>
                <span id='eyeIconLogin' class="toggle-password" onclick="togglePasswordVisibility('loginPassword', 'eyeIconLogin')">👁️</span>
            </div><br><br><button type='submit' class='btn' style='width:100%'>Se connecter</button>
        </form>
    </div></body></html>"""

# ==========================================
# ⚙️ صفحة Paramètres وتحديث حسابات الأدمن والشريك
# ==========================================
@app.route('/admin/change-year', methods=['POST'])
def change_year():
    if is_logged_in():
        new_year = request.form.get('selected_year')
        if new_year:
            session['selected_year'] = new_year
    redirect_to = request.form.get('redirect_to', '/admin')
    return redirect(redirect_to)

@app.route('/admin/update-partner', methods=['POST'])
def update_partner():
    if not is_full_admin():
        return redirect('/admin')
        
    new_username = request.form.get('partner_username', '').strip()
    new_password = request.form.get('partner_password', '').strip()
    confirm_password = request.form.get('confirm_partner_password', '').strip()

    if not new_password or new_password != confirm_password:
        return redirect('/admin/settings?partner_msg=error')

    partner_user = query_db("SELECT id FROM users WHERE role = 'partner'", fetchone=True)
    h_pass = generate_password_hash(new_password)

    if partner_user:
        query_db("UPDATE users SET username = ?, password = ? WHERE id = ?", (new_username, h_pass, partner_user[0]), commit=True)
    else:
        query_db("INSERT INTO users (username, password, role) VALUES (?, ?, 'partner')", (new_username, h_pass), commit=True)

    return redirect('/admin/settings?partner_msg=success')

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not is_full_admin(): return redirect('/admin')
    msg_success, msg_error = "", ""
    if request.method == 'POST':
        u_match = query_db("SELECT * FROM users WHERE username = ?", (session.get('username', 'admin'),), fetchone=True)
        if not u_match or not check_password_hash(u_match[2], request.form['old_password']):
            msg_error = "❌ Ancien mot de passe incorrect !"
        elif request.form['new_password'] != request.form['confirm_password']:
            msg_error = "❌ Les nouveaux mots de passe ne correspondent pas !"
        else:
            query_db("UPDATE users SET username = ?, password = ? WHERE id = ?", (request.form['new_username'], generate_password_hash(request.form['new_password']), u_match[0]), commit=True)
            session['username'] = request.form['new_username']
            msg_success = "✅ Identifiants mis à jour avec succès !"

    partner_status = request.args.get('partner_msg')
    partner_msg_html = ""
    if partner_status == 'success':
        partner_msg_html = "<p style='color:green; text-align:center; font-weight:bold; margin-bottom:15px;'>✅ Identifiants Associé mis à jour avec succès !</p>"
    elif partner_status == 'error':
        partner_msg_html = "<p style='color:red; text-align:center; font-weight:bold; margin-bottom:15px;'>❌ Mots de passe غير متطابقين !</p>"

    partner_account = query_db("SELECT username FROM users WHERE role = 'partner'", fetchone=True)
    current_partner_username = partner_account[0] if partner_account else "shrik"

    current_year = get_current_year()
    
    db_years = query_db("SELECT DISTINCT strftime('%Y', date_debut) FROM reservations WHERE date_debut IS NOT NULL UNION SELECT DISTINCT strftime('%Y', strftime('%Y-%m-%d', mois || '-01')) FROM autres_charges WHERE mois IS NOT NULL ORDER BY 1 DESC", fetchall=True)
    available_years = [y[0] for y in db_years if y[0]]
    
    default_years = [str(y) for y in range(2023, 2031)]
    all_years_set = sorted(list(set(available_years + default_years)), reverse=True)

    options_years = "".join([f"<option value='{yr}' {'selected' if yr == current_year else ''}>{yr}</option>" for yr in all_years_set])

    return f"""<html><head><title>Paramètres - UXURYCAR</title>{STYLE}</head><body>{nav()}<div class='container' style='max-width:600px;'>
        <div class="card" style="background:white; padding:25px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.05); margin-bottom:25px;">
            <h3 style="color:#111424; margin-bottom:10px;">📅 Année d'exercice (السنة الشغالة)</h3>
            <p style="color:#777; font-size:13px; margin-bottom:15px;">اختر السنة التي تريد عرض وتصفح بياناتها في النظام :</p>
            <form method="POST" action="/admin/change-year" style="display:flex; gap:10px; align-items:center;">
                <select name="selected_year" style="font-weight:bold; max-width:200px;">
                    {options_years}
                </select>
                <button type="submit" class="btn" style="background-color:#e94560;">Changer l'année</button>
            </form>
        </div>

        <div class='form-container' style='margin:0 0 25px 0;'>
            <h2>⚙️ Modifier les Identifiants Admin</h2>
            <p style='color:green; text-align:center; font-weight:bold; margin-bottom:15px;'>{msg_success}</p>
            <p style='color:red; text-align:center; font-weight:bold; margin-bottom:15px;'>{msg_error}</p>
            <form method='POST'>
                <label>Nom d'utilisateur (Login)</label><input type='text' name='new_username' value='{session.get("username", "admin")}' required>
                <label>Ancien mot de passe</label>
                <div class="password-container"><input type='password' id='oldPass' name='old_password' required><span id='eyeOld' class="toggle-password" onclick="togglePasswordVisibility('oldPass', 'eyeOld')">👁️</span></div>
                <label>Nouveau mot de passe</label>
                <div class="password-container"><input type='password' id='newPass' name='new_password' required><span id='eyeNew' class="toggle-password" onclick="togglePasswordVisibility('newPass', 'eyeNew')">👁️</span></div>
                <label>Confirmer le nouveau mot de passe</label>
                <div class="password-container"><input type='password' id='confirmPass' name='confirm_password' required><span id='eyeConfirm' class="toggle-password" onclick="togglePasswordVisibility('confirmPass', 'eyeConfirm')">👁️</span></div>
                <br><br><button type='submit' class='btn' style='width:100%; background-color:#17a2b8;'>🔒 Enregistrer le nouveau mot de passe</button>
            </form>
        </div>

        <div class='form-container' style='margin:0;'>
            <h2>🤝 Modifier les Identifiants Associé (الشريك)</h2>
            {partner_msg_html}
            <form action="/admin/update-partner" method="POST">
                <label>Nom d'utilisateur (Login)</label>
                <input type="text" name="partner_username" value="{current_partner_username}" required>
                
                <label>Nouveau mot de passe</label>
                <div class="password-container">
                    <input type="password" id="pPass" name="partner_password" required>
                    <span id="eyeP" class="toggle-password" onclick="togglePasswordVisibility('pPass', 'eyeP')">👁️</span>
                </div>
                
                <label>Confirmer le nouveau mot de passe</label>
                <div class="password-container">
                    <input type="password" id="confirmPPass" name="confirm_partner_password" required>
                    <span id="eyeConfirmP" class="toggle-password" onclick="togglePasswordVisibility('confirmPPass', 'eyeConfirmP')">👁️</span>
                </div>
                <br><br>
                <button type="submit" class="btn" style="width:100%; background-color:#ffc107; color:#212529;">🔒 Enregistrer les identifiants Associé</button>
            </form>
        </div>

    </div></body></html>"""

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect('/')

@app.route('/admin/voitures/modifier/<int:id_voiture>', methods=['GET', 'POST'])
def modifier_voiture(id_voiture):
    if not is_full_admin(): return redirect('/admin')
    voiture = get_voiture_by_id(id_voiture)
    if not voiture: return redirect('/admin/voitures')
        
    if request.method == 'POST':
        nom_image = voiture[6]
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = os.path.splitext(secure_filename(file.filename))[1]
                nom_image = f"{uuid.uuid4().hex}{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], nom_image))

        query_db('''UPDATE voitures SET nom = ?, prix_jour = ?, type = ?, places = ?, transmission = ?, image = ?, disponible = ? WHERE id = ?''',
                 (request.form['nom'], request.form['prix_jour'], request.form['type'], request.form['places'], request.form['transmission'], nom_image, request.form['disponible'], id_voiture), commit=True)
        return redirect('/admin/voitures')

    return f"""<html><head>{STYLE}</head><body>{nav()}<div class='form-container'>
        <h2>Modifier la Voiture : {voiture[1]}</h2>
        <form method='POST' enctype='multipart/form-data'>
            <label>Modèle</label><input type='text' name='nom' value='{voiture[1]}' required>
            <label>Prix par jour (DH)</label><input type='number' name='prix_jour' value='{voiture[2]}' required>
            <label>Carburant</label><select name='type'>
                <option {'selected' if voiture[3] == 'Diesel' else ''}>Diesel</option>
                <option {'selected' if voiture[3] == 'Essence' else ''}>Essence</option>
                <option {'selected' if voiture[3] == 'Hybride' else ''}>Hybride</option>
            </select>
            <label>Places</label><input type='number' name='places' value='{voiture[4]}' required>
            <label>Boîte de vitesse</label><select name='transmission'>
                <option {'selected' if voiture[5] == 'Manuelle' else ''}>Manuelle</option>
                <option {'selected' if voiture[5] == 'Automatique' else ''}>Automatique</option>
            </select>
            <label>Statut de la voiture</label><select name='disponible'>
                <option value='1' {'selected' if voiture[7] == 1 else ''}>Disponible</option>
                <option value='0' {'selected' if voiture[7] == 0 else ''}>Louée / Non Disponible</option>
            </select>
            <label>📸 Changer la photo (Optionnel)</label><input type='file' name='image_file' accept='image/*'><br><small style='color:#777;'>Photo actuelle: {voiture[6]}</small><br><br>
            <button type='submit' class='btn' style='width:100%; background-color:#ffc107; color:#212529;'>💾 Sauvegarder les modifications</button>
        </form>
    </div></body></html>"""

@app.route('/admin/voitures/supprimer/<int:id_voiture>')
def supprimer_voiture(id_voiture):
    if not is_full_admin(): return redirect('/admin')
    query_db('DELETE FROM voitures WHERE id = ?', (id_voiture,), commit=True)
    return redirect('/admin/voitures')

@app.route('/admin/ajouter-voiture', methods=['GET', 'POST'])
def ajouter_voiture():
    if not is_full_admin(): return redirect('/admin')
    msg = ""
    if request.method == 'POST':
        nom_image = 'default.jpg'
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = os.path.splitext(secure_filename(file.filename))[1]
                nom_image = f"{uuid.uuid4().hex}{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], nom_image))

        query_db('INSERT INTO voitures (nom, prix_jour, type, places, transmission, image, disponible) VALUES (?, ?, ?, ?, ?, ?, 1)',
                 (request.form['nom'], request.form['prix_jour'], request.form['type'], request.form['places'], request.form['transmission'], nom_image), commit=True)
        msg = "✅ Véhicule ajouté avec succès !"
        
    return f"""<html><head>{STYLE}</head><body>{nav()}<div class='form-container'>
        <h2>➕ Ajouter une Voiture</h2><p style='color:green; text-align:center; font-weight:bold; margin-bottom:15px;'>{msg}</p>
        <form method='POST' enctype='multipart/form-data'>
            <label>Modèle</label><input type='text' name='nom' required>
            <label>Prix par jour (DH)</label><input type='number' name='prix_jour' required>
            <label>Carburant</label><select name='type'><option>Diesel</option><option>Essence</option><option>Hybride</option></select>
            <label>Places</label><input type='number' name='places' value='5' required>
            <label>Boîte de vitesse</label><select name='transmission'><option>Manuelle</option><option>Automatique</option></select>
            <label>📸 Photo</label><input type='file' name='image_file' accept='image/*' required><br><br>
            <button type='submit' class='btn' style='width:100%'>Ajouter la voiture</button>
        </form>
    </div></body></html>"""

if __name__ == '__main__':
    app.run(debug=True)