import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField
from wtforms.validators import InputRequired, Length, ValidationError, DataRequired, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tyt-mojno-napisat-lubuyu-stroku-dlya-shifrovaniya')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
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
    role = db.Column(db.String(20), default='student')  # admin, teacher, student
    grade = db.Column(db.Integer, nullable=True)  # только для учеников (какой класс)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_quests = db.Column(db.String(500), default="")  # строка с ID выполненных заданий через запятую

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def complete_quest(self, quest_id):
        """Отметить задание как выполненное (добавить ID в список)"""
        if self.completed_quests:
            completed = self.completed_quests.split(',')
        else:
            completed = []
        if str(quest_id) not in completed:
            completed.append(str(quest_id))
            self.completed_quests = ','.join(completed)
            db.session.commit()
            return True
        return False

    def is_quest_completed(self, quest_id):
        """Проверить, выполнено ли задание"""
        if self.completed_quests:
            return str(quest_id) in self.completed_quests.split(',')
        return False

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_student(self):
        return self.role == 'student'


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.Integer, nullable=False)  # для какого класса
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(200), nullable=False)  # ответ для проверки
    description = db.Column(db.String(200), nullable=False)  # краткое описание для карточки
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # кто создал (null = системное)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # связь с пользователем-создателем (удобно для шаблонов)
    creator = db.relationship('User', foreign_keys=[creator_id])


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- ФУНКЦИЯ ДЛЯ СОЗДАНИЯ СТАНДАРТНЫХ ЗАДАНИЙ (ВЫЗЫВАЕТСЯ ПРИ ЗАПУСКЕ) ---
def create_default_quests():
    # Стандартные задания (бывший QUEST_DATA)
    default_quests = [
        # 1 класс
        (1, "Сколько яблок на картинке? 🍎🍎🍎 (Ответ напиши цифрой)", "3", "Сосчитай фрукты"),
        (1, "Какая фигура похожа на мяч? (напиши: круг, квадрат или треугольник)", "круг", "Найди форму"),
        (1, "Что больше: 5 или 3? (напиши число)", "5", "Сравни числа"),
        (1, "Продолжи ряд: 2, 4, 6, ... (напиши следующее число)", "8", "Продолжи ряд"),
        (1, "Сколько углов у треугольника? (напиши цифру)", "3", "Найди отличия"),
        # 2 класс
        (2, "Сколько будет 7 + 8? (напиши число)", "15", "Сложение в пределах 20"),
        (2, "Сколько будет 15 - 9? (напиши число)", "6", "Вычитание"),
        (2, "Реши пример: 3 + 4 - 2 = ?", "5", "Примеры в два действия"),
        (2, "У Маши было 5 конфет, а у Пети на 3 больше. Сколько конфет у Пети?", "8", "Задачи на логику"),
        (2, "Сколько сторон у квадрата? (напиши число)", "4", "Геометрические фигуры"),
        # 3 класс
        (3, "Сколько будет 4 * 3? (напиши число)", "12", "Таблица умножения на 2,3,4"),
        (3, "Сколько будет 6 * 7? (напиши число)", "42", "Таблица умножения на 5,6,7"),
        (3, "Сколько будет 12 * 3? (напиши число)", "36", "Внетабличное умножение"),
        (3, "Раздели 17 на 3 с остатком. Напиши остаток.", "2", "Деление с остатком"),
        (3, "В одной коробке 8 карандашей. Сколько карандашей в 5 коробках?", "40", "Задачи на умножение"),
        # 4 класс
        (4, "Реши уравнение: x + 5 = 12. Чему равен x?", "7", "Реши уравнение"),
        (4, "Что больше: 1/2 или 1/4? (напиши дробь)", "1/2", "Сравни дроби"),
        (4, "Поезд едет со скоростью 60 км/ч. Сколько км он проедет за 3 часа?", "180", "Задачи на движение"),
        (4, "Вычисли: 10 - 2 * 3 = ?", "4", "Порядок действий"),
        (4, "Загадка: стоит в поле дуб, на дубе 3 ветки, на каждой ветке по 2 яблока. Сколько всего яблок? (напиши число)", "0", "Математический ребус"),
    ]

    for grade, question, answer, description in default_quests:
        # Проверяем, есть ли уже такое задание (по вопросу, чтобы не дублировать)
        exist = Quest.query.filter_by(question=question).first()
        if not exist:
            q = Quest(grade=grade, question=question, answer=answer, description=description, creator_id=None)
            db.session.add(q)
    db.session.commit()


# --- ФУНКЦИЯ ДЛЯ СОЗДАНИЯ АДМИНА (ЕСЛИ НЕТ) ---
def create_admin():
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(username=admin_username, role='admin')
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin created: {admin_username} / {admin_password}")


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


class CreateTeacherForm(FlaskForm):
    username = StringField('Имя учителя', validators=[InputRequired(), Length(min=3, max=20)])
    password = PasswordField('Пароль', validators=[InputRequired(), Length(min=3, max=20)])
    submit = SubmitField('Создать учителя')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Пользователь с таким именем уже существует.')


class CreateQuestForm(FlaskForm):
    grade = IntegerField('Класс (1-4)', validators=[DataRequired(), NumberRange(min=1, max=4)])
    description = StringField('Краткое описание (для карточки)', validators=[InputRequired(), Length(max=200)])
    question = TextAreaField('Текст задания', validators=[InputRequired()])
    answer = StringField('Правильный ответ', validators=[InputRequired(), Length(max=200)])
    submit = SubmitField('Создать задание')


# --- КОНТЕКСТНЫЙ ПРОЦЕССОР ДЛЯ ТЕКУЩЕГО ГОДА ---
@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}


# --- ДЕКОРАТОРЫ ДЛЯ ПРОВЕРКИ РОЛЕЙ ---
def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def teacher_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not (current_user.is_teacher or current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


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
        new_user = User(username=form.username.data, role='student')
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
    # В зависимости от роли показываем разную стартовую страницу
    if current_user.is_admin:
        return redirect(url_for('admin_panel'))
    elif current_user.is_teacher:
        return redirect(url_for('teacher_dashboard'))
    else:
        return render_template('dashboard.html', user=current_user)


# ----- АДМИН ПАНЕЛЬ -----
@app.route('/admin')
@admin_required
def admin_panel():
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin_panel.html', teachers=teachers)


@app.route('/admin/create_teacher', methods=['GET', 'POST'])
@admin_required
def create_teacher():
    form = CreateTeacherForm()
    if form.validate_on_submit():
        teacher = User(username=form.username.data, role='teacher')
        teacher.set_password(form.password.data)
        db.session.add(teacher)
        db.session.commit()
        flash(f'Учитель {form.username.data} успешно создан', 'success')
        return redirect(url_for('admin_panel'))
    return render_template('create_teacher.html', form=form)


# ----- УЧИТЕЛЬСКАЯ ПАНЕЛЬ -----
@app.route('/teacher')
@teacher_required
def teacher_dashboard():
    # Показываем список заданий, созданных этим учителем
    my_quests = Quest.query.filter_by(creator_id=current_user.id).all()
    return render_template('teacher_dashboard.html', quests=my_quests)


@app.route('/teacher/create_quest', methods=['GET', 'POST'])
@teacher_required
def create_quest():
    form = CreateQuestForm()
    if form.validate_on_submit():
        quest = Quest(
            grade=form.grade.data,
            description=form.description.data,
            question=form.question.data,
            answer=form.answer.data,
            creator_id=current_user.id
        )
        db.session.add(quest)
        db.session.commit()
        flash('Задание успешно создано', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('create_quest.html', form=form)


@app.route('/teacher/edit_quest/<int:quest_id>', methods=['GET', 'POST'])
@teacher_required
def edit_quest(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    # Проверяем, что это задание принадлежит текущему учителю
    if quest.creator_id != current_user.id and not current_user.is_admin:
        abort(403)
    form = CreateQuestForm(obj=quest)  # предзаполняем форму данными из quest
    if form.validate_on_submit():
        quest.grade = form.grade.data
        quest.description = form.description.data
        quest.question = form.question.data
        quest.answer = form.answer.data
        db.session.commit()
        flash('Задание обновлено', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('edit_quest.html', form=form, quest=quest)


@app.route('/teacher/delete_quest/<int:quest_id>')
@teacher_required
def delete_quest(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    if quest.creator_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(quest)
    db.session.commit()
    flash('Задание удалено', 'success')
    return redirect(url_for('teacher_dashboard'))


# ----- ОБЩИЕ МАРШРУТЫ ДЛЯ ЗАДАНИЙ (УЧЕНИКИ И УЧИТЕЛЯ) -----
@app.route('/quests/<int:grade>')
@login_required
def quests(grade):
    # Если пользователь ученик, запоминаем его класс
    if current_user.is_student:
        if current_user.grade != grade:
            current_user.grade = grade
            db.session.commit()
    # Для учителя и админа тоже можно показывать задания (они могут решать)
    # Получаем все задания для данного класса (стандартные + созданные учителями)
    quest_list = Quest.query.filter_by(grade=grade).all()
    return render_template('quests.html', grade=grade, user=current_user, quests=quest_list)


@app.route('/quest/<int:quest_id>', methods=['GET', 'POST'])
@login_required
def quest_detail(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    if request.method == 'POST':
        user_answer = request.form.get('answer', '').strip().lower()
        correct_answer = str(quest.answer).lower()
        if user_answer == correct_answer:
            current_user.complete_quest(quest.id)
            flash('Правильно! Ты молодец!', 'success')
            return redirect(url_for('quests', grade=quest.grade))
        else:
            flash('Неправильно, попробуй ещё раз!', 'danger')
            return render_template('quest_detail.html', quest=quest)
    return render_template('quest_detail.html', quest=quest)


# --- СОЗДАНИЕ ТАБЛИЦ И НАЧАЛЬНЫХ ДАННЫХ ПРИ ЗАПУСКЕ ---
with app.app_context():
    db.create_all()
    create_default_quests()
    create_admin()

if __name__ == '__main__':
    app.run(debug=True)