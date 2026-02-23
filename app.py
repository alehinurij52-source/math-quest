import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tyt-mojno-napisat-lubuyu-stroku-dlya-shifrovaniya'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_quests = db.Column(db.String(500), default="")  

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def complete_quest(self, grade, quest_id):
        quest_key = f"{grade}_{quest_id}"
        if self.completed_quests:
            completed = self.completed_quests.split(',')
        else:
            completed = []
        if quest_key not in completed:
            completed.append(quest_key)
            self.completed_quests = ','.join(completed)
            db.session.commit()
            return True
        return False

    def is_quest_completed(self, grade, quest_id):
        if self.completed_quests:
            quest_key = f"{grade}_{quest_id}"
            return quest_key in self.completed_quests.split(',')
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ДАННЫЕ КВЕСТОВ ---
QUEST_DATA = {
    "1_1": {"question": "Сколько яблок на картинке? 🍎🍎🍎 (Ответ напиши цифрой)", "answer": "3", "description": "Сосчитай фрукты"},
    "1_2": {"question": "Какая фигура похожа на мяч? (напиши: круг, квадрат или треугольник)", "answer": "круг", "description": "Найди форму"},
    "1_3": {"question": "Что больше: 5 или 3? (напиши число)", "answer": "5", "description": "Сравни числа"},
    "1_4": {"question": "Продолжи ряд: 2, 4, 6, ... (напиши следующее число)", "answer": "8", "description": "Продолжи ряд"},
    "1_5": {"question": "Сколько углов у треугольника? (напиши цифру)", "answer": "3", "description": "Найди отличия"},
    "2_1": {"question": "Сколько будет 7 + 8? (напиши число)", "answer": "15", "description": "Сложение в пределах 20"},
    "2_2": {"question": "Сколько будет 15 - 9? (напиши число)", "answer": "6", "description": "Вычитание"},
    "2_3": {"question": "Реши пример: 3 + 4 - 2 = ?", "answer": "5", "description": "Примеры в два действия"},
    "2_4": {"question": "У Маши было 5 конфет, а у Пети на 3 больше. Сколько конфет у Пети?", "answer": "8", "description": "Задачи на логику"},
    "2_5": {"question": "Сколько сторон у квадрата? (напиши число)", "answer": "4", "description": "Геометрические фигуры"},
    "3_1": {"question": "Сколько будет 4 * 3? (напиши число)", "answer": "12", "description": "Таблица умножения на 2,3,4"},
    "3_2": {"question": "Сколько будет 6 * 7? (напиши число)", "answer": "42", "description": "Таблица умножения на 5,6,7"},
    "3_3": {"question": "Сколько будет 12 * 3? (напиши число)", "answer": "36", "description": "Внетабличное умножение"},
    "3_4": {"question": "Раздели 17 на 3 с остатком. Напиши остаток.", "answer": "2", "description": "Деление с остатком"},
    "3_5": {"question": "В одной коробке 8 карандашей. Сколько карандашей в 5 коробках?", "answer": "40", "description": "Задачи на умножение"},
    "4_1": {"question": "Реши уравнение: x + 5 = 12. Чему равен x?", "answer": "7", "description": "Реши уравнение"},
    "4_2": {"question": "Что больше: 1/2 или 1/4? (напиши дробь)", "answer": "1/2", "description": "Сравни дроби"},
    "4_3": {"question": "Поезд едет со скоростью 60 км/ч. Сколько км он проедет за 3 часа?", "answer": "180", "description": "Задачи на движение"},
    "4_4": {"question": "Вычисли: 10 - 2 * 3 = ?", "answer": "4", "description": "Порядок действий"},
    "4_5": {"question": "Загадка: стоит в поле дуб, на дубе 3 ветки, на каждой ветке по 2 яблока. Сколько всего яблок? (напиши число)", "answer": "0", "description": "Математический ребус"},
}

# --- ФОРМЫ ---
class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[InputRequired(), Length(min=3, max=20)])
    password = PasswordField('Пароль', validators=[InputRequired(), Length(min=3, max=20)])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Это имя уже занято. Придумайте другое.')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[InputRequired()])
    password = PasswordField('Пароль', validators=[InputRequired()])
    submit = SubmitField('Войти')

# --- КОНТЕКСТНЫЙ ПРОЦЕССОР ДЛЯ ТЕКУЩЕГО ГОДА ---
@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}

# --- МАРШРУТЫ ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    return render_template('index.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь войдите.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/quests/<int:grade>')
@login_required
def quests(grade):
    if current_user.grade != grade:
        current_user.grade = grade
        db.session.commit()
    return render_template('quests.html', grade=grade, user=current_user, QUEST_DATA=QUEST_DATA)

@app.route('/quest/<int:grade>/<int:quest_id>', methods=['GET', 'POST'])
@login_required
def quest(grade, quest_id):
    quest_key = f"{grade}_{quest_id}"
    if quest_key not in QUEST_DATA:
        flash('Такого задания не существует', 'danger')
        return redirect(url_for('quests', grade=grade))
    
    quest_info = QUEST_DATA[quest_key]
    
    if request.method == 'POST':
        user_answer = request.form.get('answer', '').strip().lower()
        correct_answer = str(quest_info['answer']).lower()
        
        if user_answer == correct_answer:
            current_user.complete_quest(grade, quest_id)
            flash('Правильно! Ты молодец!', 'success')
            return redirect(url_for('quests', grade=grade))
        else:
            flash('Неправильно, попробуй ещё раз!', 'danger')
            return render_template('quest_detail.html', grade=grade, quest_id=quest_id, quest=quest_info)
    
    return render_template('quest_detail.html', grade=grade, quest_id=quest_id, quest=quest_info)

# --- СОЗДАНИЕ ТАБЛИЦ БАЗЫ ДАННЫХ ПРИ ЗАПУСКЕ ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)