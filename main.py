from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import os

app = Flask(__name__, static_folder='.', static_url_path='')

# 🛠️ მონაცემთა ბაზის კონფიგურაცია
app.config['SECRET_KEY'] = 'gansakutrebulad_saidumlo_gasagebi'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders_final_v6.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login კონფიგურაცია
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'registracia'


# --- 1. მონაცემთა ბაზის მოდელები ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    selected_products = db.Column(db.Text, nullable=True, default="[]")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    product_price = db.Column(db.String(50), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    buyer_name = db.Column(db.String(100), nullable=False)
    card_number = db.Column(db.String(20), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


# --- 2. WTForms ფორმა ყიდვის გვერდისთვის (Checkout) ---
class CheckoutForm(FlaskForm):
    buyer_name = StringField('სახელი და გვარი', validators=[DataRequired(message="სახელის შეყვანა სავალდებულოა")])
    card_number = StringField('ბარათის ნომერი', validators=[Length(max=20)])
    submit = SubmitField('დადასტურება')


# --- 3. დამხმარე ფუნქცია ფაილების წასაკითხად templates საქაღალდედან ---
def render_and_fix_html(filename, inject_script="", **context):
    file_path = os.path.join('templates', filename)

    # თუ templates-ში არ არის, შეამოწმოს მთავარ საქაღალდეშიც
    if not os.path.exists(file_path):
        file_path = filename

    if not os.path.exists(file_path):
        return f"<h3>შეცდომა: ფაილი სახელით '{filename}' ვერ მოიძებნა! შეამოწმე სახელი.</h3>"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # JavaScript-ის ხარვეზების გასწორება propail.html-ში
    if filename == 'propail.html':
        content = content.replace('showAsOwned("Bssed hair clay");', 'showAsOwned("hair clay");')
        content = content.replace('if(product === "hair clay") showAsOwned("Bssed hair clay");',
                                  'if(product === "hair clay" || product === "Bssed hair clay") showAsOwned("Bssed hair clay");')

    # localStorage სკრიპტის ჩასმა
    if inject_script:
        content = content.replace('</head>', f'{inject_script}\n</head>')

    return render_template_string(content, **context)


# --- 4. საიტის მისამართები (Routes) ---

@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/shop.html')
def shop():
    return send_from_directory('.', 'shop.html')


# არჩევანის გვერდი (მივუთითეთ ზუსტად serceva.html)
@app.route('/serceva.html', methods=['GET', 'POST'])
def arceva():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.first() or User(username="guest@tbc.ge", password="password123", selected_products="[]")
        if not user.id:
            db.session.add(user)
            db.session.commit()

    if request.method == 'POST':
        selected_list = request.form.getlist('products')
        user.selected_products = json.dumps(selected_list if selected_list else [])
        db.session.commit()
        return redirect(url_for('profile'))

    user_products = json.loads(user.selected_products) if user.selected_products else []

    inject_script = f"""
    <script>
        localStorage.setItem("isRegistered", "true");
        localStorage.setItem("myProducts", '{json.dumps(user_products)}');
    </script>
    """
    # 🛠️ აქ ჩავწერე შენი ფაილის სახელი: serceva.html
    return render_and_fix_html('serceva.html', inject_script, user_products=user_products)


# პროფილის გვერდი
@app.route('/propili.html', methods=['GET', 'POST'])
def profile():
    form = CheckoutForm()

    if current_user.is_authenticated:
        user = current_user
        email = user.username
        username = email.split('@')[0]
    else:
        user = User.query.first()
        email = user.username if user else "guest@tbc.ge"
        username = email.split('@')[0] if user else "სტუმარი"

    user_products = json.loads(user.selected_products) if (user and user.selected_products) else []

    product_name = request.args.get('name', 'უცნობი პროდუქტი')
    product_price = request.args.get('price', '0.00')

    if form.validate_on_submit():
        new_order = Order(
            product_name=product_name,
            product_price=product_price,
            payment_method=request.form.get('payment_method', 'Cash'),
            buyer_name=form.buyer_name.data,
            card_number=form.card_number.data if form.card_number.data else "N/A"
        )
        db.session.add(new_order)
        db.session.commit()
        return redirect(url_for('gamces'))

    inject_script = f"""
    <script>
        localStorage.setItem("isRegistered", "true");
        localStorage.setItem("userEmail", "{email}");
        localStorage.setItem("myProducts", '{json.dumps(user_products)}');
    </script>
    """
    return render_and_fix_html('propail.html', inject_script, form=form, username=username, email=email, user_products=user_products)


@app.route('/registracia.html', methods=['GET', 'POST'])
def registracia():
    if request.method == 'POST':
        input_username = request.form.get('username') or request.form.get('email')
        input_password = request.form.get('password')

        if input_username and input_password:
            user = User.query.filter_by(username=input_username).first()
            if not user:
                user = User(username=input_username, password=input_password, selected_products="[]")
                db.session.add(user)
                db.session.commit()

            login_user(user)
            return redirect(url_for('profile'))

    return send_from_directory('.', 'registracia.html')


@app.route('/final')
@app.route('/final.html')
def final_page():
    return send_from_directory('.', 'final.html')


@app.route('/games.html')
@app.route('/gamces.html')
def gamces():
    return send_from_directory('.', 'games.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)