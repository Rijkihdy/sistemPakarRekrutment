from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, PasswordField
from wtforms.validators import DataRequired
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = 's3cr3tkey'

# ================================
# LOGIN PROTECTOR
# ================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# =========================
# CERTAINTY FACTOR
# =========================

def combine_cf(cf1, cf2):
    if cf1 >= 0 and cf2 >= 0:
        return cf1 + cf2 * (1 - cf1)
    if cf1 < 0 and cf2 < 0:
        return cf1 + cf2 * (1 + cf1)
    return (cf1 + cf2) / 2

def calculate_cf(experience, education, skills, culture_fit, job_position_id):

    CF_EXPERIENCE_EXPERT = 0.9
    CF_EDUCATION_EXPERT = 0.8
    CF_SKILLS_EXPERT = 0.85
    CF_CULTURE_EXPERT = 0.75

    if experience == '5+':
        cf_exp_user = 1.0
    elif experience == '3-5':
        cf_exp_user = 0.7
    else:
        cf_exp_user = 0.4

    qualifications = ''
    required_skills = ''

    if job_position_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM JobPositions WHERE id = ?", (job_position_id,))
        job = cur.fetchone()
        conn.close()

        if job:
            qualifications = job['qualifications'] or ''
            required_skills = job['required_skills'] or ''

    tokens = [t.strip().upper() for t in qualifications.split(',') if t.strip()]
    edu_ok = (education or '').upper() in tokens
    cf_edu_user = 1.0 if edu_ok else 0.0

    req_list = [s.strip().lower() for s in required_skills.split(',') if s.strip()]
    skills_text = (skills or '').lower()
    skill_ok = any(req in skills_text for req in req_list) if req_list else False
    cf_skill_user = 1.0 if skill_ok else 0.0

    cf_culture_user = 1.0 if culture_fit.lower() == "yes" else 0.0

    cf_exp = CF_EXPERIENCE_EXPERT * cf_exp_user
    cf_edu = CF_EDUCATION_EXPERT * cf_edu_user
    cf_skill = CF_SKILLS_EXPERT * cf_skill_user
    cf_culture = CF_CULTURE_EXPERT * cf_culture_user

    cf_total = combine_cf(cf_exp, cf_edu)
    cf_total = combine_cf(cf_total, cf_skill)
    cf_total = combine_cf(cf_total, cf_culture)

    cf_total = max(min(cf_total, 1.0), -1.0)
    return round(cf_total, 3)

# =========================
# DATABASE FUNCTIONS
# =========================

def get_db_connection():
    conn = sqlite3.connect('recruitment_system.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_candidates():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT Candidates.*, JobPositions.title AS job_title
        FROM Candidates
        LEFT JOIN JobPositions ON Candidates.job_position_id = JobPositions.id
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def save_candidate(name, experience, education, skills, culture_fit, job_position_id, owner):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO Candidates (name, experience, education, skills, culture_fit, job_position_id, owner)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, experience, education, skills, culture_fit, job_position_id, owner))
    conn.commit()
    conn.close()


def get_job_positions():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM JobPositions')
    jobs = cur.fetchall()
    conn.close()
    return jobs

def get_results():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT Results.id AS result_id, Results.candidate_id,
               Candidates.name, Candidates.experience, Candidates.education,
               Candidates.skills, Candidates.culture_fit,
               JobPositions.title AS position_title,
               Results.cf, Results.recommendation
        FROM Results
        JOIN Candidates ON Results.candidate_id = Candidates.id
        LEFT JOIN JobPositions ON Candidates.job_position_id = JobPositions.id
        ORDER BY Results.id DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows

def save_job_position(title, description, qualifications, required_skills):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO JobPositions (title, description, qualifications, required_skills) VALUES (?, ?, ?, ?)',
        (title, description, qualifications, required_skills)
    )
    conn.commit()
    conn.close()

def save_result(candidate_id, job_position_id, cf, recommendation):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO Results (candidate_id, job_position_id, cf, recommendation)
        VALUES (?, ?, ?, ?)
    ''', (candidate_id, job_position_id, cf, recommendation))
    conn.commit()
    conn.close()

# =========================
# LOGIN SYSTEM
# =========================

USER_CREDENTIALS = {
    "admin": {
        "password": "password123",
        "role": "admin",
        "candidate_id": None   # admin tidak punya kandidat
    },
    "user1": {
        "password": "userpass",
        "role": "user",
        "candidate_id": 1      # user1 hanya boleh lihat kandidat ID 1
    },
    "user2": {
        "password": "abcd1234",
        "role": "user",
        "candidate_id": 2
    }
}


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

@app.route('/', methods=['GET'])
def home():
    return redirect(url_for('login'))   # <-- HALAMAN PERTAMA = LOGIN

@app.route('/index')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = USER_CREDENTIALS.get(username)

        if USER_CREDENTIALS.get(username) and USER_CREDENTIALS[username]["password"] == password:
            session['username'] = username
            session['role'] = USER_CREDENTIALS[username]["role"]
            session['candidate_id'] = USER_CREDENTIALS[username]["candidate_id"]
            return redirect(url_for('dashboard'))


        return render_template('login.html', form=form, error="Invalid username or password")

    return render_template('login.html', form=form)

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return "Akses ditolak. Hanya admin.", 403
        return f(*args, **kwargs)
    return wrapper


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# =========================
# DASHBOARD + PROTECTED ROUTES
# =========================
@app.route('/dashboard')
@login_required
def dashboard():
    username = session["username"]

    # =====================
    # Jika admin → dashboard lengkap
    # =====================
    if username == "admin":
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM Candidates) AS total_candidates,
                (SELECT COUNT(*) FROM JobPositions) AS total_positions,
                (SELECT COUNT(*) FROM Candidates WHERE job_position_id IS NOT NULL) AS candidates_with_position,
                (SELECT COUNT(*) FROM Results) AS total_results,
                (SELECT ROUND(AVG(cf), 3) FROM Results) AS average_cf,
                (SELECT COUNT(*) FROM Results WHERE recommendation = 'Kandidat sangat cocok untuk posisi ini.') AS recommended_count,
                (SELECT COUNT(*) FROM Results WHERE recommendation = 'Kandidat kurang cocok untuk posisi ini.') AS not_recommended_count,
                (SELECT COUNT(*) FROM Candidates WHERE LOWER(culture_fit) = 'yes') AS culture_fit_yes
        """)

        stats = cur.fetchone()
        conn.close()

        return render_template('dashboard.html',
                               username=username,
                               stats=stats)

   
    # Jika user biasa → dashboard khusus user
    # =====================
    conn = get_db_connection()
    cur = conn.cursor()

    # Ambil kandidat milik user
    cur.execute("SELECT * FROM Candidates WHERE owner = ?", (username,))
    user_data = cur.fetchone()

    # Jika user belum isi data → tampilkan pesan kosong
    if not user_data:
        return render_template(
            "dashboard_user.html",
            username=username,
            user_stats=None
        )

    # Ambil hasil seleksi milik user ini
    cur.execute("SELECT * FROM Results WHERE candidate_id = ?", (user_data["id"],))
    result = cur.fetchone()

    conn.close()

    return render_template(
        "dashboard_user.html",
        username=username,
        user_stats=result,
        candidate=user_data
    )


@app.route('/data_kandidat')
@login_required
def data_kandidat():

    if session["role"] == "admin":
        candidates = get_candidates()  # semua data
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM Candidates WHERE owner = ?", (session['username'],))
        candidates = cur.fetchall()
        conn.close()

    return render_template('data_kandidat.html', candidates=candidates)


@app.route('/data_posisi')
@login_required
def data_posisi():
    job_positions = get_job_positions()
    return render_template('data_posisi.html', job_positions=job_positions)


@app.route('/results')
@login_required
def results():

    if session["role"] == "admin":
        data = get_results()
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM Results
            WHERE candidate_id IN (
                SELECT id FROM Candidates WHERE owner = ?
            )
        """, (session['username'],))
        data = cur.fetchall()
        conn.close()

    return render_template('results.html', results=data)


@app.route('/add_candidate', methods=['GET', 'POST'])
@login_required
def add_candidate():
    form = CandidateForm()
    form.job_position.choices = [(j['id'], j['title']) for j in get_job_positions()]

    if form.validate_on_submit():
        save_candidate(
            form.name.data,
            form.experience.data,
            form.education.data,
            form.skills.data,
            form.culture_fit.data,
            form.job_position.data,
            session["username"]   # <---- TAMBAHKAN INI
        )
        return redirect(url_for('data_kandidat'))

    return render_template('add_candidate.html', form=form)

@app.route('/add_job_position', methods=['GET', 'POST'])
@login_required
@admin_required
def add_job_position():
    form = JobPositionForm()
    if form.validate_on_submit():
        save_job_position(
            form.title.data, form.description.data,
            form.qualifications.data, form.required_skills.data
        )
        return redirect(url_for('data_posisi'))
    return render_template('add_job_position.html', form=form)

@app.route('/process_selection/<int:candidate_id>/<int:job_position_id>')
@login_required
def process_selection(candidate_id, job_position_id):

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Candidates WHERE id = ?", (candidate_id,))
    cand = cur.fetchone()

    applied_job = cand["job_position_id"]

    cur.execute("SELECT * FROM JobPositions WHERE id = ?", (applied_job,))
    job = cur.fetchone()
    conn.close()

    cf = calculate_cf(cand['experience'], cand['education'], cand['skills'], cand['culture_fit'], applied_job)

    recommendation = ("Posisi yang dipilih sangat cocok."
                      if cf >= 0.95 else
                      "Posisi yang dipilih kurang cocok.")

    save_result(candidate_id, applied_job, cf, recommendation)

    return redirect(url_for('data_kandidat'))

@app.route('/delete_candidate/<int:candidate_id>', methods=['POST'])
@login_required
# @admin_required
def delete_candidate(candidate_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Hapus hasil seleksi yang terkait
    cur.execute("DELETE FROM Results WHERE candidate_id = ?", (candidate_id,))

    # Hapus kandidat
    cur.execute("DELETE FROM Candidates WHERE id = ?", (candidate_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('data_kandidat'))

@app.route('/delete_job_position/<int:job_position_id>', methods=['POST'])
@login_required
@admin_required
def delete_job_position(job_position_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Hapus kandidat yang memakai posisi ini
    cur.execute("UPDATE Candidates SET job_position_id = NULL WHERE job_position_id = ?", (job_position_id,))

    # Hapus posisi kerja
    cur.execute("DELETE FROM JobPositions WHERE id = ?", (job_position_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('data_posisi'))

@app.route('/delete_result/<int:result_id>', methods=['POST'])
@login_required
def delete_result(result_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM Results WHERE id = ?", (result_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('results'))

# Formulir untuk input data kandidat
class CandidateForm(FlaskForm):
    name = StringField('Nama Kandidat', validators=[DataRequired()])
    experience = SelectField('Pengalaman Kerja', choices=[('<1', 'Kurang dari 1 tahun'), ('3-5', '3-5 tahun'), ('5+', 'Lebih dari 5 tahun')], validators=[DataRequired()])
    education = SelectField('Pendidikan', choices=[('S1', 'S1'), ('S2', 'S2')], validators=[DataRequired()])
    skills = StringField('Keterampilan', validators=[DataRequired()])
    culture_fit = SelectField('Kesesuaian dengan Budaya Perusahaan', choices=[('yes', 'Sesuai'), ('no', 'Tidak Sesuai')], validators=[DataRequired()])
    job_position = SelectField('Posisi yang Dilamar', coerce=int)  # Input untuk posisi pekerjaan
    submit = SubmitField('Simpan Kandidat')

# Formulir untuk input data posisi pekerjaan
class JobPositionForm(FlaskForm):
    title = StringField('Judul Posisi', validators=[DataRequired()])
    description = StringField('Deskripsi Pekerjaan', validators=[DataRequired()])
    qualifications = StringField('Kualifikasi Posisi', validators=[DataRequired()])
    required_skills = StringField('Keterampilan yang Dibutuhkan', validators=[DataRequired()])
    submit = SubmitField('Simpan Posisi')


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
