from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/db_gestion_contrats_maintenance'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Make date available in all templates
@app.context_processor
def inject_date():
    return {'date': date, 'datetime': datetime, 'timedelta': timedelta}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'utilisateurs'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_utilisateur = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contrats_geres = db.relationship('Contract', backref='gestionnaire', lazy=True)

class Supplier(db.Model):
    __tablename__ = 'fournisseurs'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(20))
    adresse = db.Column(db.Text)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contrats = db.relationship('Contract', backref='fournisseur', lazy=True)

class Equipment(db.Model):
    __tablename__ = 'equipements'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    numero_serie = db.Column(db.String(100))
    date_acquisition = db.Column(db.Date)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Association table for many-to-many relationship
contrat_equipement = db.Table('contrat_equipement',
    db.Column('contrat_id', db.Integer, db.ForeignKey('contrats.id'), primary_key=True),
    db.Column('equipement_id', db.Integer, db.ForeignKey('equipements.id'), primary_key=True)
)

class Contract(db.Model):
    __tablename__ = 'contrats'
    
    id = db.Column(db.Integer, primary_key=True)
    fournisseur_id = db.Column(db.Integer, db.ForeignKey('fournisseurs.id'), nullable=False)
    gestionnaire_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=False)
    reference_marche = db.Column(db.String(100), nullable=False)
    date_debut = db.Column(db.Date, nullable=False)
    date_fin_garantie = db.Column(db.Date, nullable=False)
    date_fin_maintenance = db.Column(db.Date, nullable=False)
    frequence_visite_preventive = db.Column(db.String(20), default='trimestrielle')
    delai_reponse_intervention_heures = db.Column(db.Integer, default=2)
    statut = db.Column(db.String(20), default='actif')
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    equipements = db.relationship('Equipment', secondary=contrat_equipement, lazy='subquery',
                                 backref=db.backref('contrats', lazy=True))
    interventions = db.relationship('Intervention', backref='contrat', lazy=True)
    pvs = db.relationship('PV', backref='contrat', lazy=True)

class Intervention(db.Model):
    __tablename__ = 'interventions'
    
    id = db.Column(db.Integer, primary_key=True)
    contrat_id = db.Column(db.Integer, db.ForeignKey('contrats.id'), nullable=False)
    equipement_id = db.Column(db.Integer, db.ForeignKey('equipements.id'))
    type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date_intervention = db.Column(db.DateTime, nullable=False)
    date_prevue_preventive = db.Column(db.Date)
    statut = db.Column(db.String(20), default='en_cours')
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    equipement = db.relationship('Equipment', backref='interventions')
    pvs = db.relationship('PV', backref='intervention', lazy=True)

class PV(db.Model):
    __tablename__ = 'pvs'
    
    id = db.Column(db.Integer, primary_key=True)
    contrat_id = db.Column(db.Integer, db.ForeignKey('contrats.id'), nullable=False)
    intervention_id = db.Column(db.Integer, db.ForeignKey('interventions.id'))
    type = db.Column(db.String(50), nullable=False)
    date_signature = db.Column(db.Date, nullable=False)
    reserves = db.Column(db.Text)
    chemin_document = db.Column(db.String(255))
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    mis_a_jour_le = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Routes
@app.route('/')
@login_required
def dashboard():
    # Redirect to the appropriate dashboard based on user role
    if current_user.role == 'Admin':
        return redirect(url_for('dashboard_admin'))
    elif current_user.role == 'Gestionnaire de Contrat':
        return redirect(url_for('dashboard_contract_manager'))
    elif current_user.role == 'Gestionnaire Technique':
        return redirect(url_for('dashboard_technical_manager'))
    else:
        flash("Rôle utilisateur inconnu.", "danger")
        return redirect(url_for('logout'))

@app.route('/dashboard/admin')
@login_required
def dashboard_admin():
    # ...statistics and queries as in your main dashboard...
    total_contracts = Contract.query.count()
    active_contracts = Contract.query.filter_by(statut='actif').count()
    total_equipment = Equipment.query.count()
    pending_interventions = Intervention.query.filter_by(statut='en_cours').count()
    recent_interventions = Intervention.query.order_by(Intervention.date_intervention.desc()).limit(5).all()
    thirty_days_later = date.today() + timedelta(days=30)
    expiring_contracts = Contract.query.filter(Contract.date_fin_maintenance <= thirty_days_later).all()
    return render_template('dashboard_admin.html',
        total_contracts=total_contracts,
        active_contracts=active_contracts,
        total_equipment=total_equipment,
        pending_interventions=pending_interventions,
        recent_interventions=recent_interventions,
        expiring_contracts=expiring_contracts
    )

@app.route('/dashboard/contract_manager')
@login_required
def dashboard_contract_manager():
    # ...statistics and queries as in your main dashboard...
    total_contracts = Contract.query.count()
    active_contracts = Contract.query.filter_by(statut='actif').count()
    total_equipment = Equipment.query.count()
    pending_interventions = Intervention.query.filter_by(statut='en_cours').count()
    recent_interventions = Intervention.query.order_by(Intervention.date_intervention.desc()).limit(5).all()
    thirty_days_later = date.today() + timedelta(days=30)
    expiring_contracts = Contract.query.filter(Contract.date_fin_maintenance <= thirty_days_later).all()
    return render_template('dashboard_contract_manager.html',
        total_contracts=total_contracts,
        active_contracts=active_contracts,
        total_equipment=total_equipment,
        pending_interventions=pending_interventions,
        recent_interventions=recent_interventions,
        expiring_contracts=expiring_contracts
    )

@app.route('/dashboard/technical_manager')
@login_required
def dashboard_technical_manager():
    # ...statistics and queries as in your main dashboard...
    total_contracts = Contract.query.count()
    active_contracts = Contract.query.filter_by(statut='actif').count()
    total_equipment = Equipment.query.count()
    pending_interventions = Intervention.query.filter_by(statut='en_cours').count()
    recent_interventions = Intervention.query.order_by(Intervention.date_intervention.desc()).limit(5).all()
    thirty_days_later = date.today() + timedelta(days=30)
    expiring_contracts = Contract.query.filter(Contract.date_fin_maintenance <= thirty_days_later).all()
    return render_template('dashboard_technical_manager.html',
        total_contracts=total_contracts,
        active_contracts=active_contracts,
        total_equipment=total_equipment,
        pending_interventions=pending_interventions,
        recent_interventions=recent_interventions,
        expiring_contracts=expiring_contracts
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(nom_utilisateur=username).first()
        
        if user and check_password_hash(user.mot_de_passe_hash, password):
            login_user(user)
            # Redirect to the correct dashboard after login
            if user.role == 'Admin':
                return redirect(url_for('dashboard_admin'))
            elif user.role == 'Gestionnaire de Contrat':
                return redirect(url_for('dashboard_contract_manager'))
            elif user.role == 'Gestionnaire Technique':
                return redirect(url_for('dashboard_technical_manager'))
            else:
                flash("Rôle utilisateur inconnu.", "danger")
                return redirect(url_for('logout'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Supplier routes
@app.route('/suppliers')
@login_required
def suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        supplier = Supplier(
            nom=request.form['nom'],
            email=request.form['email'],
            telephone=request.form.get('telephone'),
            adresse=request.form.get('adresse')
        )
        db.session.add(supplier)
        db.session.commit()
        flash('Supplier added successfully!', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('suppliers/form.html')

@app.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    
    if request.method == 'POST':
        supplier.nom = request.form['nom']
        supplier.email = request.form['email']
        supplier.telephone = request.form.get('telephone')
        supplier.adresse = request.form.get('adresse')
        db.session.commit()
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('suppliers'))
    
    return render_template('suppliers/form.html', supplier=supplier)

@app.route('/suppliers/delete/<int:id>')
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    db.session.delete(supplier)
    db.session.commit()
    flash('Supplier deleted successfully!', 'success')
    return redirect(url_for('suppliers'))

# Equipment routes
@app.route('/equipment')
@login_required
def equipment():
    equipment = Equipment.query.all()
    return render_template('equipment/list.html', equipment=equipment)

@app.route('/equipment/add', methods=['GET', 'POST'])
@login_required
def add_equipment():
    if request.method == 'POST':
        equipment = Equipment(
            nom=request.form['nom'],
            type=request.form['type'],
            description=request.form.get('description'),
            numero_serie=request.form.get('numero_serie'),
            date_acquisition=datetime.strptime(request.form['date_acquisition'], '%Y-%m-%d').date() if request.form.get('date_acquisition') else None
        )
        db.session.add(equipment)
        db.session.commit()
        flash('Equipment added successfully!', 'success')
        return redirect(url_for('equipment'))
    
    equipment_types = ['serveur', 'switch_san', 'baie_disques', 'nas', 'chassis_rack', 'switch', 'routeur', 'pare_feu', 'climatiseur', 'onduleur', 'groupe_electrogene', 'lot_consommables', 'logiciel']
    return render_template('equipment/form.html', equipment_types=equipment_types)

@app.route('/equipment/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    
    if request.method == 'POST':
        equipment.nom = request.form['nom']
        equipment.type = request.form['type']
        equipment.description = request.form.get('description')
        equipment.numero_serie = request.form.get('numero_serie')
        equipment.date_acquisition = datetime.strptime(request.form['date_acquisition'], '%Y-%m-%d').date() if request.form.get('date_acquisition') else None
        db.session.commit()
        flash('Equipment updated successfully!', 'success')
        return redirect(url_for('equipment'))
    
    equipment_types = ['serveur', 'switch_san', 'baie_disques', 'nas', 'chassis_rack', 'switch', 'routeur', 'pare_feu', 'climatiseur', 'onduleur', 'groupe_electrogene', 'lot_consommables', 'logiciel']
    return render_template('equipment/form.html', equipment=equipment, equipment_types=equipment_types)

@app.route('/equipment/delete/<int:id>')
@login_required
def delete_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    db.session.delete(equipment)
    db.session.commit()
    flash('Equipment deleted successfully!', 'success')
    return redirect(url_for('equipment'))

# Contract routes
@app.route('/contracts')
@login_required
def contracts():
    contracts = Contract.query.all()
    return render_template('contracts/list.html', contracts=contracts)

@app.route('/contracts/add', methods=['GET', 'POST'])
@login_required
def add_contract():
    if request.method == 'POST':
        contract = Contract(
            fournisseur_id=int(request.form['fournisseur_id']),
            gestionnaire_id=current_user.id,
            reference_marche=request.form['reference_marche'],
            date_debut=datetime.strptime(request.form['date_debut'], '%Y-%m-%d').date(),
            date_fin_garantie=datetime.strptime(request.form['date_fin_garantie'], '%Y-%m-%d').date(),
            date_fin_maintenance=datetime.strptime(request.form['date_fin_maintenance'], '%Y-%m-%d').date(),
            frequence_visite_preventive=request.form['frequence_visite_preventive'],
            delai_reponse_intervention_heures=int(request.form.get('delai_reponse_intervention_heures', 2))
        )
        
        # Add selected equipment
        equipment_ids = request.form.getlist('equipment_ids')
        for eq_id in equipment_ids:
            equipment = Equipment.query.get(int(eq_id))
            if equipment:
                contract.equipements.append(equipment)
        
        db.session.add(contract)
        db.session.commit()
        flash('Contract added successfully!', 'success')
        return redirect(url_for('contracts'))
    
    suppliers = Supplier.query.all()
    equipment = Equipment.query.all()
    return render_template('contracts/form.html', suppliers=suppliers, equipment=equipment)

@app.route('/pv/add', methods=['GET', 'POST'])
@login_required
def add_pv():
    if current_user.role != 'Gestionnaire Technique' and current_user.role != 'Admin':
        flash("Accès refusé.", "danger")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        # Minimal logic for demonstration
        # You should implement actual PV creation logic here
        flash('PV ajouté avec succès !', 'success')
        return redirect(url_for('dashboard_technical_manager'))
    return render_template('pv/form.html')

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_manage_users():
    if current_user.role != 'Admin':
        flash("Accès refusé.", "danger")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role')
        print("DEBUG: username:", username)
        print("DEBUG: email:", email)
        print("DEBUG: password:", password)
        print("DEBUG: role:", role)
        if not role:
            flash("Le rôle est obligatoire.", "danger")
            return redirect(url_for('admin_manage_users'))
        if User.query.filter_by(nom_utilisateur=username).first():
            flash("Nom d'utilisateur déjà utilisé.", "danger")
        else:
            user = User(
                nom_utilisateur=username,
                email=email,
                role=role,
                mot_de_passe_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            # Fetch back and print for debug
            created_user = User.query.filter_by(nom_utilisateur=username).first()
            print("DEBUG: created user role in DB:", created_user.role)
            flash("Utilisateur créé avec succès.", "success")
        return redirect(url_for('admin_manage_users'))
    users = User.query.all()
    return render_template('admin_manage_users.html', users=users)

@app.route('/interventions')
@login_required
def view_interventions():
    # You can fetch and pass interventions as needed
    interventions = Intervention.query.all()
    return render_template('interventions/list.html', interventions=interventions)

# Initialize database and create admin user
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create admin user if it doesn't exist
        admin = User.query.filter_by(nom_utilisateur='admin').first()
        if not admin:
            admin = User(
                nom_utilisateur='admin',
                email='admin@steg.tn',
                role='admin',
                mot_de_passe_hash=generate_password_hash('admin123')
            )
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)