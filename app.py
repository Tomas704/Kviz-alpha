from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt 
import os
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from flask_login import (LoginManager, UserMixin, login_user, logout_user, current_user, login_required)
import json
from flask_wtf.file import FileField, FileAllowed, FileRequired
from flask import Response
from wtforms import TextAreaField, IntegerField, SelectField, BooleanField
from wtforms.validators import NumberRange
from datetime import datetime
import random
from flask import Flask, render_template, url_for, flash, redirect, request, session
import math
from wtforms import MultipleFileField

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config['SECRET_KEY'] = 'pSjYgGAJu4577*#js$qCSnD56fNxG8beuV!Y$$gQgEA4@$M4%@9Aqoq96DYy2m!r3mbS3@QG!VDspJHfkqx8goGU3L5ZBoNqKba%C4Hyn!U9rT%wLA6Uu6zPmEKuaGiV'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Pre zobrazenie tejto stránky sa musíte prihlásiť.'
login_manager.login_message_category = 'info'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    # NOVÝ RIADOK: Vzťah k tabuľke Quiz
    # backref='author' znamená, že v Kvíze budeme môcť použiť 'quiz.author' 
    # a dostaneme objekt používateľa.   
    quizzes = db.relationship('Quiz', backref='author', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    category = db.Column(db.String(50), default='Všeobecné', nullable=False)
    description = db.Column(db.Text, nullable=True) # Popis kvízu
    
    # Časovače (0 = vypnuté / neobmedzené)
    time_limit_seconds = db.Column(db.Integer, default=0) 
    time_per_question_seconds = db.Column(db.Integer, default=0)
    
    # Zobrazenie a Navigácia
    # 'all_at_once' = Všetky otázky pod sebou
    # 'one_by_one' = Jedna otázka na stránku
    display_mode = db.Column(db.String(20), default='all_at_once') 
    
    # Tieto nastavenia platia hlavne pre 'one_by_one'
    allow_backtracking = db.Column(db.Boolean, default=True) # Možnosť vrátiť sa späť
    strict_time_limit = db.Column(db.Boolean, default=True)
    
    # Náhodnosť
    shuffle_questions = db.Column(db.Boolean, default=False) # Premiešať otázky
    shuffle_options = db.Column(db.Boolean, default=False)   # Premiešať odpovede (ABCD)
    
    # Vyhodnotenie
    passing_score = db.Column(db.Integer, default=50) # Hranica úspešnosti v %
    show_explanations = db.Column(db.Boolean, default=True) # Zobraziť vysvetlenia po teste

    questions = db.relationship('Question', backref='quiz', lazy=True, cascade="all, delete-orphan")
    results = db.relationship('QuizResult', backref='quiz', lazy=True, cascade="all, delete-orphan")

    @property
    def total_attempts(self):
        """Vráti celkový počet spustení tohto testu."""
        return len(self.results)

    @property
    def avg_percentage(self):
        """Vráti priemernú úspešnosť (v %) alebo 0, ak test nikto nerobil."""
        if not self.results:
            return 0
        total = sum(r.percentage for r in self.results)
        return round(total / len(self.results), 1)

    def __repr__(self):
        return f'<Quiz {self.title}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False) # Text otázky
    
    # Typ otázky: 'single' (jedna možnosť), 'multi' (viac možností), 'text' (dopĺňanie)
    q_type = db.Column(db.String(20), nullable=False, default='single')
    # Body za otázku (default = 1)
    points = db.Column(db.Integer, default=1)
    # Cudzí kľúč: Odkazujeme na ID v tabuľke 'quiz'
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    # Kedy bola otázka vytvorená
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    #Poradie otázky (default 0)
    position = db.Column(db.Integer, default=0)

    explanation = db.Column(db.Text, nullable=True) # HTML text vysvetlenia

    is_active = db.Column(db.Boolean, default=True)
    
    # Vzťah: Otázka má veľa možností (odpovedí)
    options = db.relationship('Option', backref='question', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Question {self.text[:30]}...>'

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False) # Text odpovede
    is_correct = db.Column(db.Boolean, default=False) # Je táto odpoveď správna?
    
    # Cudzí kľúč: Odkazujeme na ID v tabuľke 'question'
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

    def __repr__(self):
        return f'<Option {self.text}>'

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)     # Získané body
    max_score = db.Column(db.Integer, nullable=False) # Maximálne možné body
    percentage = db.Column(db.Float, nullable=False)  # Percentuálna úspešnosť
    date_taken = db.Column(db.DateTime, default=datetime.utcnow) # Kedy to robil
    time_spent = db.Column(db.Integer, nullable=True)
    time_limit_seconds_snapshot = db.Column(db.Integer, default=0)
    display_mode_snapshot = db.Column(db.String(20), default='all_at_once')
    allow_backtracking_snapshot = db.Column(db.Boolean, default=True)
    
    # Kto to robil
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Aký kvíz
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    
    # Vzťahy pre jednoduchší prístup
    user = db.relationship('User', backref='results', lazy=True)
    # Pridávame tento vzťah, aby sme mohli zapnúť kaskádu
    answers = db.relationship('UserAnswer', backref='quiz_result', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Result {self.score}/{self.max_score}>'
    
class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Ku ktorému výsledku táto odpoveď patrí
    quiz_result_id = db.Column(db.Integer, db.ForeignKey('quiz_result.id'), nullable=False)
    
    # Na ktorú otázku odpovedal
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    
    # A) Ak vybral možnosť (Single/Multi), uložíme ID možnosti
    option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=True)
    
    # B) Ak písal text, uložíme text
    text_answer = db.Column(db.Text, nullable=True)

    question = db.relationship('Question', lazy=True)

    def __repr__(self):
        return f'<Ans Q:{self.question_id}>'

@login_manager.user_loader
def load_user(user_id):
    # Táto funkcia povie Flask-Login, ako nájsť používateľa podľa jeho ID
    return User.query.get(int(user_id))

class RegistrationForm(FlaskForm):
    username = StringField('Používateľské meno', 
                           validators=[
                               DataRequired(message='Používateľské meno je povinné.'), 
                               Length(min=4, max=32, message='Meno musí mať 4 až 32 znakov.')
                           ])
    
    password = PasswordField('Heslo', 
                             validators=[
                                 DataRequired(message='Heslo je povinné.'), 
                                 Length(min=8, message='Heslo musí mať aspoň 8 znakov.')
                             ])
    
    confirm_password = PasswordField('Potvrďte heslo', 
                                     validators=[
                                         DataRequired(message='Potvrdenie hesla je povinné.'), 
                                         EqualTo('password', message='Heslá sa musia zhodovať.')    
                                     ])
    
    submit = SubmitField('Zaregistrovať sa')

    def validate_username(self, username):
        """
        Automaticky volaná metóda, ktorá overí, či
        používateľské meno (username.data) už nie je v databáze.
        """
        # Použijeme náš 'User' model na vyhľadanie v databáze
        user = User.query.filter_by(username=username.data).first()
        if user:
            # Ak sme niekoho našli, vyhodíme validačnú chybu
            raise ValidationError('Toto používateľské meno je už obsadené. Zvoľte si iné.')
        
class LoginForm(FlaskForm):
    username = StringField('Používateľské meno', 
                           validators=[DataRequired(message='Zadajte používateľské meno.')])
    
    password = PasswordField('Heslo', 
                             validators=[DataRequired(message='Zadajte heslo.')])
    
    submit = SubmitField('Prihlásiť sa')

class QuizForm(FlaskForm):
    title = StringField('Názov kvízu', validators=[DataRequired(message='Zadajte názov kvízu.')])
    category = StringField('Kategória', default='Všeobecné', validators=[DataRequired()])
    submit = SubmitField('Vytvoriť kvíz')

class ImportQuizForm(FlaskForm):
    # Povolíme len súbory s koncovkou .json
    files = MultipleFileField('Vyber JSON súbory', validators=[
        DataRequired()
        # FileAllowed tu niekedy robí problémy pri multiple poliach, 
        # kontrolu prípony spravíme radšej manuálne v logike.
    ])
    submit = SubmitField('Nahrať a Importovať')

class ImportQuestionForm(FlaskForm):
    files = MultipleFileField('Vyber JSON súbory otázok', validators=[
        DataRequired()
    ])
    submit = SubmitField('Nahrať a pridať')

class QuizSettingsForm(FlaskForm):
    title = StringField('Názov kvízu', validators=[DataRequired()])
    category = StringField('Kategória', validators=[DataRequired()])
    description = TextAreaField('Popis kvízu (voliteľné)')
    
    # --- POLIA PRE CELKOVÝ ČAS (H : M : S) ---
    total_h = IntegerField('Hod', default=0, validators=[NumberRange(min=0)])
    total_m = IntegerField('Min', default=0, validators=[NumberRange(min=0, max=59)])
    total_s = IntegerField('Sek', default=0, validators=[NumberRange(min=0, max=59)])
    
    # --- POLIA PRE LIMIT NA OTÁZKU (M : S) ---
    # (Hodiny na jednu otázku sú zbytočné, stačia minúty a sekundy)
    question_m = IntegerField('Min', default=0, validators=[NumberRange(min=0)])
    question_s = IntegerField('Sek', default=0, validators=[NumberRange(min=0, max=59)])
    
    # # Nastavenia času
    # time_limit_seconds = IntegerField('Celkový časový limit (sekundy)', 
    #                                   default=0, 
    #                                   validators=[NumberRange(min=0)],
    #                                   description="Zadajte 0 pre neobmedzený čas.")
    
    # time_per_question_seconds = IntegerField('Limit na jednu otázku (sekundy)', 
    #                                          default=0,
    #                                          validators=[NumberRange(min=0)],
    #                                          description="Zadajte 0 pre vypnutie.")
    
    strict_time_limit = BooleanField(
        'Prísny časový limit (Automatické odoslanie)',
        description="Ak je vypnuté, užívateľ môže pokračovať aj po limite (zaznamená sa nadčas)."
    )
    
    # Zobrazenie
    display_mode = SelectField('Formát zobrazenia', choices=[
        ('all_at_once', 'Všetky otázky naraz (pod sebou)'),
        ('one_by_one', 'Po jednej otázke (krokovanie)')
    ])
    
    allow_backtracking = BooleanField('Povoliť návrat k predošlým otázkam')
    
    # Náhodnosť a skóre
    shuffle_questions = BooleanField('Náhodné poradie otázok')
    shuffle_options = BooleanField('Náhodné poradie odpovedí (pre ABCD)')
    
    passing_score = IntegerField('Hranica úspešnosti (%)', 
                                 default=50, 
                                 validators=[NumberRange(min=0, max=100)])
    
    show_explanations = BooleanField('Zobraziť vysvetlenia odpovedí po vyhodnotení')

    submit = SubmitField('Uložiť nastavenia')

class QuestionForm(FlaskForm):
    text = TextAreaField('Znenie otázky', validators=[DataRequired(message="Zadajte text otázky.")])
    explanation = TextAreaField('Vysvetlenie (zobrazí sa po vyhodnotení)')
    
    q_type = SelectField('Typ otázky', choices=[
        ('single', 'Jedna správna odpoveď (ABCD)'),
        ('multi', 'Viac správnych odpovedí (Checkboxy)'),
        ('text', 'Dopĺňanie slova (Text)')
    ])
    
    points = IntegerField('Počet bodov', default=1, validators=[NumberRange(min=0)])
    
    submit = SubmitField('Uložiť otázku')

def recalculate_quiz_score(quiz):
    """
    Pomocná funkcia: Prepočíta skóre všetkých výsledkov daného kvízu
    podľa aktuálneho nastavenia otázok a odpovedí.
    """
    print(f"🔄 Spúšťam automatický prepočet pre kvíz: {quiz.title}")
    
    for result in quiz.results:
        new_score = 0
        new_max_score = 0
        
        # 1. Mapovanie odpovedí užívateľa pre rýchle hľadanie
        # { question_id: [zoznam_id_odpovedi] } a { question_id: text }
        answers_map = {}
        text_answers_map = {}
        
        # Zoznam otázok, ktoré boli v TOMTO výsledku
        questions_in_this_result = set()

        for ans in result.answers:
            questions_in_this_result.add(ans.question) # Pridáme objekt otázky
            if ans.option_id:
                if ans.question_id not in answers_map:
                    answers_map[ans.question_id] = []
                answers_map[ans.question_id].append(str(ans.option_id))
            if ans.text_answer:
                text_answers_map[ans.question_id] = ans.text_answer

        # 2. Prechádzame len otázky, ktoré boli súčasťou tohto výsledku!
        # (Ignorujeme globálne quiz.questions, používame len tie z odpovedí)
        for question in questions_in_this_result:
            # PODMIENKA 2 (NOVÁ): Deaktivovaná otázka
            # Ak je otázka vypnutá, správame sa, akoby neexistovala (nezarátame max body)
            if not question.is_active:
                continue

            new_max_score += question.points
            
            # Logika bodovania (rovnaká ako pri take_quiz)
            
            # A) TEXT
            if question.q_type == 'text':
                # Bezpečne získame odpoveď (ak existuje)
                user_text = text_answers_map.get(question.id, "").strip().lower()
                # Bezpečne získame správnu odpoveď (ak existuje)
                if question.options:
                    correct_text = question.options[0].text.strip().lower()
                    if user_text == correct_text:
                        new_score += question.points
            
            # B) SINGLE CHOICE
            elif question.q_type == 'single':
                user_choices = answers_map.get(question.id, [])
                # Nájdeme správnu možnosť
                correct_option = next((o for o in question.options if o.is_correct), None)
                
                # Ak existuje správna možnosť A užívateľ ju vybral
                if correct_option and user_choices and user_choices[0] == str(correct_option.id):
                    new_score += question.points
                    
            # C) MULTI CHOICE
            elif question.q_type == 'multi':
                user_choices = set(answers_map.get(question.id, []))
                correct_ids = set([str(o.id) for o in question.options if o.is_correct])
                if user_choices == correct_ids:
                    new_score += question.points

        # 3. Uložíme nové hodnoty do výsledku
        result.score = new_score
        result.max_score = new_max_score
        result.percentage = (new_score / new_max_score * 100) if new_max_score > 0 else 0
    
    # Uložíme zmeny do DB
    db.session.commit()

@app.route('/', methods=['GET', 'POST']) # Povolíme aj POST pre rýchle vytvorenie
def index():
    # Ak používateľ nie je prihlásený, ukážeme mu len obyčajnú "landing page"
    if not current_user.is_authenticated:
        return render_template('index.html', title="Vitajte")
    
    # --- LOGIKA PRE PRIHLÁSENÉHO POUŽÍVATEĽA ---
    
    # 1. Pripravíme formulár na vytvorenie nového kvízu
    form = QuizForm()
    # Formulár na import (NOVÝ)
    import_form = ImportQuizForm()
    
    # 2. Ak odoslal formulár (chce vytvoriť kvíz)
    if form.validate_on_submit():
        quiz = Quiz(title=form.title.data, category=form.category.data, author=current_user)
        db.session.add(quiz)
        db.session.commit()
        flash('Kvíz bol vytvorený! Teraz doň pridaj otázky.', 'success')
        return redirect(url_for('index')) # Refresh stránky
    
    # 3. Načítame VŠETKY kvízy tohto používateľa
    #    Vďaka vzťahu v modeli User môžeme použiť 'current_user.quizzes'
    my_quizzes = current_user.quizzes

    # Získame zoznam unikátnych kategórií (pre filter)
    # set() odstráni duplicity, sorted() ich zoradí podľa abecedy
    categories = sorted(list(set(q.category for q in my_quizzes)))
    
    return render_template('dashboard.html', title="Moje Kvízy", form=form, import_form=import_form, quizzes=my_quizzes, categories=categories)

@app.route('/info')
def info_page():
    return render_template('info.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, 
                    password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Účet pre {form.username.data} bol úspešne vytvorený!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', title='Registrácia', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Ak je používateľ už prihlásený, pošleme ho preč z login stránky
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # 1. Nájdeme používateľa v databáze podľa mena
        user = User.query.filter_by(username=form.username.data).first()
        
        # 2. Skontrolujeme, či používateľ existuje A ČI SA HESLO ZHODUJE
        #    Použijeme bcrypt na porovnanie hesla z formulára s hashom v databáze
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            # Ak áno, prihlásime ho
            login_user(user) # Toto je tá mágia z Flask-Login
            flash('Prihlásenie bolo úspešné!', 'success')
            
            # Ak sa používateľ snažil dostať na chránenú stránku, 
            # presmerujeme ho tam, inak na 'index'
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            # Ak sa meno alebo heslo nezhoduje, zobrazíme všeobecnú chybu
            # (Z bezpečnostných dôvodov nehovoríme, či bolo zlé meno alebo heslo)
            flash('Prihlásenie zlyhalo. Skontrolujte používateľské meno a heslo.', 'danger')
            
    return render_template('login.html', title='Prihlásenie', form=form)

@app.route('/import-quiz', methods=['POST'])
@login_required
def import_quiz():
    form = ImportQuizForm()
    
    if form.validate_on_submit():
        success_count = 0
        errors = []

        # CYKLUS CEZ VŠETKY NAHRANÉ SÚBORY
        for f in form.files.data:
            # Skip ak nie je súbor vybraný alebo nemá názov
            if not f or f.filename == '':
                continue
                
            # Manuálna kontrola prípony (pre istotu)
            if not f.filename.endswith('.json'):
                errors.append(f"{f.filename}: Nie je JSON súbor")
                continue

            try:
                # Načítanie JSONu
                data = json.load(f)
                
                # --- VYTVORENIE KVÍZU ---
                new_quiz = Quiz(
                    title=data['title'],
                    author=current_user,
                    category=data.get('category', 'Všeobecné'),
                    description=data.get('description', ''),
                    
                    # Nastavenia
                    time_limit_seconds=data.get('time_limit_seconds', 0),
                    time_per_question_seconds=data.get('time_per_question_seconds', 0),
                    display_mode=data.get('display_mode', 'all_at_once'),
                    allow_backtracking=data.get('allow_backtracking', True),
                    strict_time_limit=data.get('strict_time_limit', True),
                    shuffle_questions=data.get('shuffle_questions', False),
                    shuffle_options=data.get('shuffle_options', False),
                    passing_score=data.get('passing_score', 50),
                    show_explanations=data.get('show_explanations', True)
                )
                
                db.session.add(new_quiz)
                
                # --- PRIDANIE OTÁZOK ---
                # Použijeme enumerate pre zachovanie poradia (position)
                for i, q_data in enumerate(data.get('questions', []), 1):
                    new_question = Question(
                        text=q_data['text'],
                        explanation=q_data.get('explanation', ''),
                        q_type=q_data['type'],
                        points=q_data.get('points', 1),
                        position=i, # Uložíme poradie
                        quiz=new_quiz,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(new_question)
                    
                    for o_data in q_data['options']:
                        new_option = Option(
                            text=o_data['text'],
                            is_correct=o_data['is_correct'],
                            question=new_question
                        )
                        db.session.add(new_option)
                
                success_count += 1

            except KeyError as e:
                errors.append(f"{f.filename}: Chýba kľúč {e}")
            except Exception as e:
                errors.append(f"{f.filename}: {str(e)}")
        
        # Uložíme všetko do DB naraz
        if success_count > 0:
            db.session.commit()
            flash(f'Úspešne importovaných {success_count} súborov.', 'success')
        
        # Vypíšeme chyby (ak nejaké boli)
        if errors:
            flash(f'Chyby pri importe: {"; ".join(errors)}', 'danger')
            
    return redirect(url_for('index'))

@app.route('/quiz/<int:quiz_id>/delete')
@login_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Bezpečnostná kontrola: Je to naozaj tvoj kvíz?
    if quiz.author != current_user:
        flash('Nemáte oprávnenie zmazať tento kvíz.', 'danger')
        return redirect(url_for('index'))
    
    # Zmažeme kvíz (vďaka cascade sa zmažú aj otázky)
    db.session.delete(quiz)
    db.session.commit()
    
    flash(f'Kvíz "{quiz.title}" bol úspešne zmazaný.', 'success')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    logout_user() # Mágia z Flask-Login
    flash('Boli ste úspešne odhlásený.', 'success')
    return redirect(url_for('index'))

@app.route('/quiz/<int:quiz_id>/history')
@login_required
def quiz_history(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Vytiahneme výsledky pre tohto užívateľa a tento kvíz
    # Zoradíme ich od najnovšieho (descending order)
    results = QuizResult.query.filter_by(quiz_id=quiz.id, user_id=current_user.id)\
                              .order_by(QuizResult.date_taken.desc()).all()
    
    return render_template('quiz_history.html', quiz=quiz, results=results)

@app.route('/category/rename', methods=['POST'])
@login_required
def rename_category():
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name')
    
    if not old_name or not new_name:
        flash('Chyba: Musíte zadať nový názov.', 'danger')
        return redirect(url_for('index'))
        
    if old_name == new_name:
        return redirect(url_for('index'))

    # Nájdi všetky kvízy prihláseného používateľa, ktoré majú túto starú kategóriu
    quizzes_to_update = Quiz.query.filter_by(user_id=current_user.id, category=old_name).all()
    
    if not quizzes_to_update:
        flash('Kategória sa nenašla.', 'warning')
        return redirect(url_for('index'))
    
    # Hromadná aktualizácia
    count = 0
    for q in quizzes_to_update:
        q.category = new_name
        count += 1
        
    db.session.commit()
    
    flash(f'Kategória "{old_name}" bola premenovaná na "{new_name}". ({count} aktualizovaných testov)', 'success')
    return redirect(url_for('index'))

@app.route('/result/<int:result_id>')
@login_required
def view_result(result_id):
    result = QuizResult.query.get_or_404(result_id)
    if result.user_id != current_user.id:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    # --- PRÍPRAVA DÁT ---
    user_answers_map = {}
    
    # Zoznam otázok, ktoré boli súčasťou TOHTO testu
    # (Získame ich priamo z odpovedí užívateľa)
    questions_in_test = []
    seen_questions = set()

    for ans in result.answers:
        # Mapa odpovedí (pre vyfarbovanie)
        if ans.question_id not in user_answers_map:
            user_answers_map[ans.question_id] = {'selected_options': [], 'text': None}
        
        if ans.option_id:
            user_answers_map[ans.question_id]['selected_options'].append(ans.option_id)
        if ans.text_answer is not None:
            user_answers_map[ans.question_id]['text'] = ans.text_answer
            
        # Zoznam otázok (pre výpis)
        # ans.question je objekt otázky (vďaka vzťahu v modeli)
        if ans.question_id not in seen_questions:
            questions_in_test.append(ans.question)
            seen_questions.add(ans.question_id)
    
    # Zoradíme ich podľa pozície, aby neboli napreskakčku
    questions_in_test.sort(key=lambda x: x.position)

    return render_template('result.html', 
                           result=result, 
                           quiz=result.quiz, 
                           user_map=user_answers_map,
                           questions=questions_in_test) # <-- POSIELAME NOVÝ ZOZNAM

@app.route('/export-quiz/<int:quiz_id>')
@login_required
def export_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # 1. Pripravíme hlavičku JSONu so všetkými nastaveniami
    quiz_data = {
        "title": quiz.title,
        "category": quiz.category,
        "description": quiz.description,
        
        # Časovače
        "time_limit_seconds": quiz.time_limit_seconds,
        "time_per_question_seconds": quiz.time_per_question_seconds,
        
        # Zobrazenie a Navigácia
        "display_mode": quiz.display_mode,
        "allow_backtracking": quiz.allow_backtracking,
        
        # Náhodnosť a Skóre
        "shuffle_questions": quiz.shuffle_questions,
        "shuffle_options": quiz.shuffle_options,
        "passing_score": quiz.passing_score,
        "show_explanations": quiz.show_explanations,
        
        # Zoznam otázok (toto ostáva rovnaké)
        "questions": []
    }

    # 2. Naplníme otázky
    for question in quiz.questions:
        q_dict = {
            "text": question.text,
            "explanation": question.explanation,
            "type": question.q_type,
            "points": question.points,
            "options": []
        }
        
        for option in question.options:
            o_dict = {
                "text": option.text,
                "is_correct": option.is_correct
            }
            q_dict["options"].append(o_dict)
            
        quiz_data["questions"].append(q_dict)

    json_response = json.dumps(quiz_data, indent=4, ensure_ascii=False)

    return Response(
        json_response,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename=kviz_{quiz.id}.json'}
    )

# --- ROUTY PRE MANAŽÉRA KVÍZU ---

@app.route('/quiz/<int:quiz_id>/manage/settings', methods=['GET', 'POST'])
@login_required
def manage_quiz_settings(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kontrola, či je používateľ autorom
    if quiz.author != current_user:
        flash('Nemáte oprávnenie upravovať tento kvíz.', 'danger')
        return redirect(url_for('index'))
    
    form = QuizSettingsForm(obj=quiz) # 'obj=quiz' automaticky predvyplní formulár dátami z DB!
    
    if form.validate_on_submit():
        # Uložíme zmeny z formulára do databázy
        form.populate_obj(quiz) # Funkcia, ktorá prepíše dáta z formulára do objektu
        
        # A) Celkový čas
        t_h = form.total_h.data or 0
        t_m = form.total_m.data or 0
        t_s = form.total_s.data or 0
        quiz.time_limit_seconds = (t_h * 3600) + (t_m * 60) + t_s
        
        # B) Čas na otázku
        q_m = form.question_m.data or 0
        q_s = form.question_s.data or 0
        quiz.time_per_question_seconds = (q_m * 60) + q_s

        db.session.commit()
        flash('Nastavenia kvízu boli uložené.', 'success')
        return redirect(url_for('manage_quiz_settings', quiz_id=quiz.id))
    
    # Ak formulár nebol odoslaný (prvé načítanie), naplníme ho dátami z DB
    if request.method == 'GET':
        # PREPOČET: Databáza (Sekundy) -> Formulár (H:M:S)
        # A) Celkový čas
        total_sec = quiz.time_limit_seconds
        form.total_h.data = total_sec // 3600
        form.total_m.data = (total_sec % 3600) // 60
        form.total_s.data = total_sec % 60
        
        # B) Čas na otázku
        quest_sec = quiz.time_per_question_seconds
        form.question_m.data = quest_sec // 60
        form.question_s.data = quest_sec % 60
        
    return render_template('manage_settings.html', title='Nastavenia kvízu', quiz=quiz, form=form)


@app.route('/quiz/<int:quiz_id>/manage/questions')
@login_required
def manage_quiz_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    import_form = ImportQuestionForm()
    questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.position).all()
    # Prejdeme všetky otázky a priradíme im poradové čísla 1, 2, 3...
    # Tým sa opravia všetky nuly z importu.
    changed = False
    for index, q in enumerate(questions):
        expected_position = index + 1
        if q.position != expected_position:
            q.position = expected_position
            changed = True
    
    if changed:
        db.session.commit()
    return render_template('manage_questions.html', title='Otázky kvízu', quiz=quiz, import_form=import_form, questions=questions)

@app.route('/quiz/<int:quiz_id>/question/add', methods=['GET', 'POST'])
@login_required
def add_question(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    form = QuestionForm()
    
    if form.validate_on_submit():
        max_pos = db.session.query(db.func.max(Question.position)).filter_by(quiz_id=quiz.id).scalar()
        new_position = (max_pos or 0) + 1
        # 1. Vytvoríme otázku (základné dáta z WTForms)
        question = Question(
            text=form.text.data,
            explanation=form.explanation.data,
            q_type=form.q_type.data,
            points=form.points.data,
            quiz=quiz,
            position=new_position
        )
        db.session.add(question)
        
        # 2. Spracujeme MOŽNOSTI (manuálne z request.form)
        # Získame zoznam všetkých textov odpovedí
        option_texts = request.form.getlist('option_text')
        
        # Získame zoznam indexov, ktoré sú označené ako správne
        # (HTML checkboxy posielajú hodnotu len ak sú zaškrtnuté)
        correct_indices = request.form.getlist('option_is_correct')
        
        for index, text in enumerate(option_texts):
            # Preskočíme prázdne riadky
            if not text.strip():
                continue
                
            # Zistíme, či je táto možnosť správna
            # (Porovnávame index ako string, lebo tak to príde z HTML)
            is_correct = str(index) in correct_indices
            
            option = Option(
                text=text,
                is_correct=is_correct,
                question=question
            )
            db.session.add(option)
            
        db.session.commit()
        flash('Otázka bola pridaná.', 'success')
        return redirect(url_for('manage_quiz_questions', quiz_id=quiz.id))
        
    return render_template('edit_question.html', title='Nová otázka', quiz=quiz, form=form, legend='Pridať novú otázku')

@app.route('/quiz/<int:quiz_id>/question/<int:question_id>/delete')
@login_required
def delete_question(quiz_id, question_id):
    question = Question.query.get_or_404(question_id)
    quiz = question.quiz # Uložíme si odkaz na kvíz skôr než zmažeme otázku
    # Bezpečnostná kontrola: Patrí táto otázka do kvízu, ktorý vlastní prihlásený user?
    if question.quiz.author != current_user:
        flash('Nemáte oprávnenie zmazať túto otázku.', 'danger')
        return redirect(url_for('index'))
    
    db.session.delete(question)
    db.session.commit()
    
    recalculate_quiz_score(quiz)
    flash('Otázka bola zmazaná a výsledky prepočítané.', 'success')
    return redirect(url_for('manage_quiz_questions', quiz_id=quiz_id))

@app.route('/quiz/<int:quiz_id>/question/<int:question_id>/toggle')
@login_required
def toggle_question(quiz_id, question_id):
    question = Question.query.get_or_404(question_id)
    
    if question.quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    # PREPNEME STAV (True -> False, False -> True)
    question.is_active = not question.is_active
    db.session.commit()
    
    # Automatický prepočet (aby sa body v histórii aktualizovali)
    recalculate_quiz_score(question.quiz)
    
    status = "aktivovaná" if question.is_active else "deaktivovaná"
    flash(f'Otázka bola {status}.', 'success')
    
    return redirect(url_for('manage_quiz_questions', quiz_id=quiz_id))

@app.route('/quiz/<int:quiz_id>/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question(quiz_id, question_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    question = Question.query.get_or_404(question_id)
    
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    # Naplníme formulár existujúcimi dátami otázky (text, typ, body)
    form = QuestionForm(obj=question)
    
    # Vytvoríme aj formulár pre import
    import_form = ImportQuestionForm()

    if form.validate_on_submit():
        # 1. Aktualizujeme základné údaje otázky
        form.populate_obj(question)
        
        # 2. VYMENÍME MOŽNOSTI (Stratégia: Zmazať staré -> Vytvoriť nové)
        # Najprv zmažeme všetky existujúce možnosti pre túto otázku
        for old_option in question.options:
            db.session.delete(old_option)
            
        # Teraz vytvoríme nové podľa formulára (rovnaký kód ako pri add_question)
        option_texts = request.form.getlist('option_text')
        correct_indices = request.form.getlist('option_is_correct')
        
        for index, text in enumerate(option_texts):
            if not text.strip():
                continue
            
            is_correct = str(index) in correct_indices
            
            new_option = Option(
                text=text,
                is_correct=is_correct,
                question=question
            )
            db.session.add(new_option)
            
        db.session.commit()
        recalculate_quiz_score(quiz)
        flash('Otázka bola úspešne upravená.', 'success')
        return redirect(url_for('manage_quiz_questions', quiz_id=quiz.id))
    
    # Pri GET požiadavke pošleme do šablóny aj objekt 'question', 
    # aby sme vedeli v JavaScripte vygenerovať existujúce odpovede
    return render_template('edit_question.html', 
                           title='Upraviť otázku', 
                           quiz=quiz, 
                           form=form, 
                           question=question, # Dôležité pre JS
                           import_form=import_form,
                           legend='Upraviť otázku')

# --- EXPORT JEDNEJ OTÁZKY ---
@app.route('/quiz/<int:quiz_id>/question/<int:question_id>/export')
@login_required
def export_question(quiz_id, question_id):
    question = Question.query.get_or_404(question_id)
    
    # 1. Pripravíme dáta
    question_data = {
        "text": question.text,
        "type": question.q_type,
        "points": question.points,
        "explanation": question.explanation,
        "options": []
    }
    
    for option in question.options:
        question_data["options"].append({
            "text": option.text,
            "explanation": question.explanation,
            "is_correct": option.is_correct
        })
        
    # 2. Vytvoríme JSON
    json_response = json.dumps(question_data, indent=4, ensure_ascii=False)
    
    # 3. Pošleme ako súbor
    filename = f"otazka_{question.id}.json"
    return Response(
        json_response,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )

# --- IMPORT OTÁZOK ---
@app.route('/quiz/<int:quiz_id>/question/import', methods=['POST'])
@login_required
def import_question(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))

    form = ImportQuestionForm()
    
    if form.validate_on_submit():
        success_count = 0
        errors = []

        # 1. Zistíme aktuálnu najvyššiu pozíciu, aby sme nové otázky dali na koniec
        max_pos = db.session.query(db.func.max(Question.position)).filter_by(quiz_id=quiz.id).scalar()
        current_position = max_pos or 0

        # 2. Cyklus cez všetky súbory
        for f in form.files.data:
            if not f or f.filename == '':
                continue
            
            if not f.filename.endswith('.json'):
                errors.append(f"{f.filename}: Nie je JSON")
                continue

            try:
                data = json.load(f)
                
                # Validácia kľúčov
                if 'text' not in data or 'options' not in data:
                     raise Exception("Chýba 'text' alebo 'options'")

                # Zvýšime pozíciu pre túto otázku
                current_position += 1

                # Vytvorenie otázky
                new_question = Question(
                    text=data['text'],
                    explanation=data.get('explanation', ''),
                    q_type=data.get('type', 'single'),
                    points=data.get('points', 1),
                    position=current_position, # <-- Dôležité: Každá má svoje poradové číslo
                    quiz=quiz
                )
                db.session.add(new_question)
                
                # Vytvorenie možností
                for o_data in data['options']:
                    new_option = Option(
                        text=o_data['text'],
                        is_correct=o_data['is_correct'],
                        question=new_question
                    )
                    db.session.add(new_option)
                
                success_count += 1

            except Exception as e:
                errors.append(f"{f.filename}: {str(e)}")

        # 3. Uložíme a vypíšeme výsledok
        if success_count > 0:
            db.session.commit()
            # Pre istotu zavoláme prepočet bodov (ak by sa importovali body)
            recalculate_quiz_score(quiz)
            flash(f'Úspešne pridaných {success_count} otázok.', 'success')
            
        if errors:
            flash(f'Chyby pri importe: {"; ".join(errors)}', 'danger')
            
    return redirect(url_for('manage_quiz_questions', quiz_id=quiz.id))

@app.route('/quiz/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)

    # RÁZCESTNÍK PODĽA TYPU ZOBRAZENIA
    if quiz.display_mode == 'one_by_one':
        return take_quiz_step_by_step(quiz)
    else:
        return take_quiz_all_at_once(quiz)
    
def take_quiz_all_at_once(quiz):
    if request.method == 'POST':
        # Ak tam nič nie je (napr. chyba JS), dáme 0
        try:
            time_spent_val = int(request.form.get('time_spent', 0))
        except ValueError:
            time_spent_val = 0
        
        result = QuizResult(
            score=0, 
            max_score=0, 
            percentage=0,
            user=current_user, 
            quiz=quiz,
            time_spent=time_spent_val,
            time_limit_seconds_snapshot=quiz.time_limit_seconds,
            display_mode_snapshot=quiz.display_mode,
            allow_backtracking_snapshot=quiz.allow_backtracking
        )
        db.session.add(result)
        db.session.flush() # Toto vygeneruje result.id, ktoré potrebujeme pre odpovede

        score = 0
        total_max_score = 0

        # Tým zabezpečíme, že sa do 'UserAnswer' uložia len tie, ktoré boli v teste.
        active_questions = Question.query.filter_by(quiz_id=quiz.id, is_active=True).order_by(Question.position).all()
        
        for question in active_questions:
            total_max_score += question.points
            user_answers = request.form.getlist(f'question_{question.id}')
            
            # --- ULOŽENIE ODPOVEDÍ DO DB ---
            if question.q_type == 'text':
                user_text = user_answers[0].strip() if user_answers else ""
                # Uložíme textovú odpoveď
                db.session.add(UserAnswer(
                    quiz_result_id=result.id,
                    question_id=question.id,
                    text_answer=user_text
                ))
            else:
                # Pre Single/Multi uložíme každú zakliknutú možnosť
                for ans_id in user_answers:
                    db.session.add(UserAnswer(
                        quiz_result_id=result.id,
                        question_id=question.id,
                        option_id=int(ans_id)
                    ))

            # --- LOGIKA BODOVANIA (Rovnaká ako predtým) ---
            if question.q_type == 'text':
                correct_text = question.options[0].text.strip().lower()
                user_text_lower = user_answers[0].strip().lower() if user_answers else ""
                if user_text_lower == correct_text:
                    score += question.points
            
            elif question.q_type == 'single':
                correct_option = next((o for o in question.options if o.is_correct), None)
                if correct_option and user_answers and user_answers[0] == str(correct_option.id):
                    score += question.points
            
            elif question.q_type == 'multi':
                correct_ids = [str(o.id) for o in question.options if o.is_correct]
                if set(user_answers) == set(correct_ids):
                    score += question.points
        
        # Aktualizujeme výsledky v objekte
        result.score = score
        result.max_score = total_max_score
        result.percentage = (score / total_max_score * 100) if total_max_score > 0 else 0
        
        db.session.commit()
        return redirect(url_for('view_result', result_id=result.id))
    
    # --- ČASŤ 2: ZOBRAZENIE TESTU (GET) ---
    
    # Ak je nastavené náhodné poradie otázok, zamiešame ich pre zobrazenie
    questions_to_display = Question.query.filter_by(quiz_id=quiz.id).filter(Question.is_active == True).order_by(Question.position).all()
    if quiz.shuffle_questions:
        random.shuffle(questions_to_display)
        
    # Ak je nastavené náhodné poradie odpovedí, musíme to pripraviť
    # Nemôžeme miešať priamo v objekte, lebo by sa to uložilo,
    # tak si vytvoríme pomocnú štruktúru len pre šablónu.
    for q in questions_to_display:
        # Vytvoríme si NOVÝ atribút 'display_options', ktorý nie je v databáze
        # Urobíme kópiu zoznamu pomocou list(...)
        q.display_options = list(q.options)
        
        if quiz.shuffle_options and q.q_type != 'text':
             random.shuffle(q.display_options)

    return render_template('take_quiz_all.html', quiz=quiz, questions=questions_to_display, effective_limit_seconds=quiz.time_limit_seconds)

def take_quiz_step_by_step(quiz):
    # Kľúč v session, pod ktorým si pamätáme stav pre tento konkrétny kvíz
    session_key = f'quiz_progress_{quiz.id}'
    
    # Ak je režim "Po jednej" A "Zakázaný návrat" A "Limit na otázku > 0"
    if quiz.display_mode == 'one_by_one' and not quiz.allow_backtracking and quiz.time_per_question_seconds > 0:
        # Súčet sekúnd (presne)
        effective_limit_seconds = len(quiz.questions) * quiz.time_per_question_seconds
    else:
        # Inak použijeme to, čo zadal učiteľ v nastaveniach
        effective_limit_seconds = quiz.time_limit_seconds

    # 1. INICIALIZÁCIA (Ak test ešte nebeží)
    if session_key not in session:
        # Vytvoríme prázdny výsledok v DB
        result = QuizResult(
            score=0, max_score=0, percentage=0,
            user=current_user, quiz=quiz,
            time_limit_seconds_snapshot=effective_limit_seconds,
            time_spent=0,
            display_mode_snapshot=quiz.display_mode,
            allow_backtracking_snapshot=quiz.allow_backtracking
        )
        db.session.add(result)
        db.session.commit()
        
        ordered_questions = Question.query.filter_by(quiz_id=quiz.id).filter(Question.is_active == True).order_by(Question.position).all()
        # Pripravíme poradie otázok (ak je shuffle, zamiešame IDčka)
        question_ids = [q.id for q in ordered_questions]
        if quiz.shuffle_questions:
            random.shuffle(question_ids)
            
        # Uložíme stav do session
        session[session_key] = {
            'result_id': result.id,
            'question_ids': question_ids,
            'current_index': 0,
            'start_time': datetime.utcnow().timestamp() # Pre presný časovač
        }
    
    # Načítame stav zo session
    progress = session[session_key]
    current_index = progress['current_index']
    question_ids = progress['question_ids']
    result = QuizResult.query.get(progress['result_id'])

    if not result:
        session.pop(session_key, None)
        return redirect(url_for('take_quiz', quiz_id=quiz.id))
    
    # Ak sme došli na koniec alebo nastala chyba v dátach
    if current_index >= len(question_ids):
        return finish_step_quiz(quiz, result, session_key)

    # Načítame aktuálnu otázku z DB
    current_question = Question.query.get(question_ids[current_index])

    # Vytvoríme kópiu do 'display_options'
    current_question.display_options = list(current_question.options)
    
    # Ak je zapnuté miešanie, zamiešame túto kópiu
    if quiz.shuffle_options and current_question.q_type != 'text':
        random.shuffle(current_question.display_options)

    # --- SPRACOVANIE ODPOVEDE (POST) ---
    if request.method == 'POST':
        # 1. Uložíme odpoveď na AKTUÁLNU otázku
        save_user_answer(result, current_question, request.form)
        
        # 2. Aktualizujeme čas (priebežne)
        try:
            time_spent_val = int(request.form.get('time_spent', 0))
            result.time_spent = time_spent_val
            db.session.commit()
        except:
            pass

        # 3. Navigácia
        direction = request.form.get('direction')
        
        if direction == 'next':
            progress['current_index'] += 1
        elif direction == 'prev' and quiz.allow_backtracking:
            progress['current_index'] -= 1
        elif direction == 'finish':
            # Uložíme a ukončíme
            return finish_step_quiz(quiz, result, session_key)
            
        # Uložíme zmenený index späť do session
        session.modified = True 
        return redirect(url_for('take_quiz', quiz_id=quiz.id))

    # --- PRÍPRAVA ZOBRAZENIA (GET) ---
    
    # Zistíme, či už užívateľ na túto otázku odpovedal (aby sme predvyplnili formulár)
    existing_answer = UserAnswer.query.filter_by(quiz_result_id=result.id, question_id=current_question.id).all()
    
    # Pripravíme dáta pre šablónu (čo má byť zaškrtnuté)
    selected_options = [str(a.option_id) for a in existing_answer if a.option_id]
    text_answer = existing_answer[0].text_answer if existing_answer and existing_answer[0].text_answer else ""

    return render_template('take_quiz_single.html', 
                           quiz=quiz, 
                           question=current_question, 
                           index=current_index, 
                           total=len(question_ids),
                           selected_options=selected_options,
                           text_answer=text_answer,
                           time_spent=result.time_spent or 0,
                           effective_limit_seconds=effective_limit_seconds)

# --- POMOCNÁ FUNKCIA NA UKONČENIE ---
def finish_step_quiz(quiz, result, session_key):
    # Vyhodnotíme celý test naraz (použijeme logiku prepočtu)
    recalculate_quiz_score(quiz) # Toto prepočíta VŠETKY results, ale to nevadí, je to bezpečné
    
    # Vyčistíme session
    session.pop(session_key, None)
    
    flash('Test bol úspešne dokončený.', 'success')
    return redirect(url_for('view_result', result_id=result.id))

# --- POMOCNÁ FUNKCIA NA ULOŽENIE ODPOVEDE ---
def save_user_answer(result, question, form_data):
    # Najprv zmažeme starú odpoveď na túto otázku (ak existuje)
    old_answers = UserAnswer.query.filter_by(quiz_result_id=result.id, question_id=question.id).all()
    for old in old_answers:
        db.session.delete(old)
    
    # Získame nové dáta
    user_answers = form_data.getlist(f'question_{question.id}')
    
    if question.q_type == 'text':
        user_text = user_answers[0].strip() if user_answers else ""
        db.session.add(UserAnswer(quiz_result_id=result.id, question_id=question.id, text_answer=user_text))
    else:
        for ans_id in user_answers:
            db.session.add(UserAnswer(quiz_result_id=result.id, question_id=question.id, option_id=int(ans_id)))
            
    db.session.commit()

@app.route('/quiz/<int:quiz_id>/recalculate')
@login_required
def recalculate_results(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    count = 0
    # Prejdeme všetky doterajšie výsledky tohto kvízu
    for result in quiz.results:
        new_score = 0
        new_max_score = 0
        
        # Pripravíme si mapu odpovedí tohto výsledku pre rýchle hľadanie
        # { question_id: [zvolene_moznosti_id, ...] }
        answers_map = {}
        text_answers_map = {}
        
        for ans in result.answers:
            if ans.option_id:
                if ans.question_id not in answers_map:
                    answers_map[ans.question_id] = []
                answers_map[ans.question_id].append(str(ans.option_id))
            if ans.text_answer:
                text_answers_map[ans.question_id] = ans.text_answer

        # Teraz prejdeme AKTUÁLNE otázky kvízu a znova ich obodujeme
        for question in quiz.questions:
            new_max_score += question.points
            
            # A) TEXT
            if question.q_type == 'text':
                user_text = text_answers_map.get(question.id, "").strip().lower()
                correct_text = question.options[0].text.strip().lower()
                if user_text == correct_text:
                    new_score += question.points
            
            # B) SINGLE
            elif question.q_type == 'single':
                user_choices = answers_map.get(question.id, [])
                correct_option = next((o for o in question.options if o.is_correct), None)
                if correct_option and user_choices and user_choices[0] == str(correct_option.id):
                    new_score += question.points
                    
            # C) MULTI
            elif question.q_type == 'multi':
                user_choices = set(answers_map.get(question.id, []))
                correct_ids = set([str(o.id) for o in question.options if o.is_correct])
                if user_choices == correct_ids:
                    new_score += question.points

        # Aktualizujeme výsledok
        result.score = new_score
        result.max_score = new_max_score
        result.percentage = (new_score / new_max_score * 100) if new_max_score > 0 else 0
        count += 1
        
    db.session.commit()
    flash(f'Úspešne prepočítaných {count} výsledkov podľa aktuálnych otázok.', 'success')
    
    return redirect(url_for('manage_quiz_settings', quiz_id=quiz.id))

@app.route('/quiz/<int:quiz_id>/question/<int:question_id>/move/<direction>')
@login_required
def move_question(quiz_id, question_id, direction):
    question = Question.query.get_or_404(question_id)
    if question.quiz.author != current_user:
        return redirect(url_for('index'))

    # Nájdi otázku, s ktorou sa má vymeniť
    if direction == 'up':
        target = Question.query.filter_by(quiz_id=quiz_id).filter(Question.position < question.position).order_by(Question.position.desc()).first()
    elif direction == 'down':
        target = Question.query.filter_by(quiz_id=quiz_id).filter(Question.position > question.position).order_by(Question.position.asc()).first()
    else:
        target = None

    if target:
        # Vymeníme ich poradie
        question.position, target.position = target.position, question.position
        db.session.commit()
    
    return redirect(url_for('manage_quiz_questions', quiz_id=quiz_id))

@app.route('/quiz/<int:quiz_id>/manage/stats')
@login_required
def manage_quiz_stats(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if quiz.author != current_user:
        flash('Nemáte oprávnenie.', 'danger')
        return redirect(url_for('index'))
    
    results = quiz.results
    
    # 1. ZÁKLADNÉ METRIKY
    total_attempts = len(results)
    
    # Ak ešte nie sú žiadne výsledky, pošleme flag 'no_data'
    if total_attempts == 0:
        return render_template('manage_stats.html', quiz=quiz, no_data=True)

    avg_score = sum(r.score for r in results) / total_attempts
    avg_percentage = sum(r.percentage for r in results) / total_attempts
    
    pass_count = sum(1 for r in results if r.percentage >= quiz.passing_score)
    fail_count = total_attempts - pass_count
    pass_rate = (pass_count / total_attempts) * 100
    
    # 2. ANALÝZA JEDNOTLIVÝCH OTÁZOK
    # Chceme vedieť: Ktorá otázka bola najťažšia?
    questions_stats = []
    
    # Prechádzame len aktívne otázky
    active_questions = Question.query.filter_by(quiz_id=quiz.id, is_active=True).order_by(Question.position).all()

    for question in active_questions:
        # Nájdeme všetky odpovede na túto otázku naprieč všetkými výsledkami
        all_answers = UserAnswer.query.filter_by(question_id=question.id).all()
        total_ans_count = len(all_answers)
        
        correct_ans_count = 0
        
        for ans in all_answers:
            is_correct = False
            
            # Logika overenia (zjednodušená pre štatistiku)
            if question.q_type == 'text':
                # Pri texte porovnávame stringy
                correct_text = question.options[0].text.strip().lower()
                if ans.text_answer and ans.text_answer.strip().lower() == correct_text:
                    is_correct = True
            
            elif question.q_type == 'single':
                # Pri single stačí porovnať option_id so správnou možnosťou
                correct_option = next((o for o in question.options if o.is_correct), None)
                if correct_option and ans.option_id == correct_option.id:
                    is_correct = True
                    
            elif question.q_type == 'multi':
                # Pri multi je to zložitejšie, lebo UserAnswer ukladá po jednom riadku.
                # Pre štatistiku budeme rátať ako "úspech", ak označil SPRÁVNU možnosť.
                if ans.option_id:
                    opt = Option.query.get(ans.option_id)
                    if opt and opt.is_correct:
                        is_correct = True
            
            if is_correct:
                correct_ans_count += 1
        
        # Výpočet úspešnosti otázky
        success_rate = (correct_ans_count / total_ans_count * 100) if total_ans_count > 0 else 0
        
        questions_stats.append({
            'text': question.text,
            'type': question.q_type,
            'total': total_ans_count,
            'correct': correct_ans_count,
            'rate': round(success_rate, 1)
        })
    
    # Zoradíme otázky od najťažšej (najmenšia úspešnosť)
    questions_stats.sort(key=lambda x: x['rate'])

    return render_template('manage_stats.html', 
                           quiz=quiz, 
                           total_attempts=total_attempts,
                           avg_percentage=round(avg_percentage, 1),
                           pass_rate=round(pass_rate, 1),
                           pass_count=pass_count,
                           fail_count=fail_count,
                           questions_stats=questions_stats,
                           no_data=False)

if __name__ == '__main__':
    app.run(debug=True, port=8080)