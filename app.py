from flask import Flask, render_template, request, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
import sqlite3

app = Flask(__name__)
app.secret_key = 's3cr3tkey'

# Fungsi untuk menghitung Certainty Factor (CF)
def calculate_cf(experience, education, skills, culture_fit, job_position_id):
    cf = 0

    # Pengalaman Kerja
    if experience == '5+':
        cf += 0.9
    elif experience == '3-5':
        cf += 0.7
    else:
        cf += 0.4
    
    # Pendidikan (Disesuaikan dengan posisi yang dilamar)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM JobPositions WHERE id = ?', (job_position_id,))
    job_position = c.fetchone()
    conn.close()
    # Pendidikan: buat flag 'yes'/'no' lalu perlakukan sama seperti culture_fit
    qualifications = job_position['qualifications'] or ''
    education_fit = 'yes' if (education and education.strip() and education.strip() in qualifications) else 'no'
    if education_fit == 'yes':
        cf += 0.8
    else:
        cf += 0.5

    # Keterampilan: buat flag 'yes'/'no' lalu perlakukan sama seperti culture_fit
    required_skills = job_position['required_skills'] or ''
    skills_list = [s.lower().strip() for s in required_skills.split(',') if s.strip()]
    candidate_skills_text = (skills or '').lower()
    skill_match = any(req in candidate_skills_text for req in skills_list)
    skills_fit = 'yes' if skill_match else 'no'
    if skills_fit == 'yes':
        cf += 0.8
    else:
        cf += 0.5

    # Kesesuaian Budaya (tetap menggunakan langsung nilai 'yes'/'no' dari kandidat)
    if culture_fit == 'yes':
        cf += 0.8
    else:
        cf += 0.5
    
    return cf


# Fungsi untuk mengakses database SQLite
def get_db_connection():
    conn = sqlite3.connect('recruitment_system.db')
    conn.row_factory = sqlite3.Row  # Mengembalikan hasil sebagai dictionary
    return conn

# Fungsi untuk mengambil semua data kandidat
def get_candidates():
    conn = get_db_connection()
    c = conn.cursor()
    # Ambil kandidat beserta judul posisi yang dilamar (jika ada)
    c.execute('''
        SELECT Candidates.*, JobPositions.title AS job_title
        FROM Candidates
        LEFT JOIN JobPositions ON Candidates.job_position_id = JobPositions.id
    ''')
    candidates = c.fetchall()
    conn.close()
    return candidates

def save_candidate(name, experience, education, skills, culture_fit, job_position_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO Candidates (name, experience, education, skills, culture_fit, job_position_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, experience, education, skills, culture_fit, job_position_id))
    conn.commit()
    conn.close()


# Fungsi untuk mengambil semua data posisi pekerjaan
def get_job_positions():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM JobPositions')
    job_positions = c.fetchall()
    conn.close()
    return job_positions


def get_candidates_with_latest_result():
    conn = get_db_connection()
    c = conn.cursor()
    # Ambil kandidat, judul posisi yang dilamar, dan hasil (CF & rekomendasi) terakhir jika ada
    c.execute('''
        SELECT c.*, jp.title AS job_title,
               r.cf AS cf, r.recommendation AS recommendation
        FROM Candidates c
        LEFT JOIN JobPositions jp ON c.job_position_id = jp.id
        LEFT JOIN Results r ON r.id = (
            SELECT id FROM Results WHERE candidate_id = c.id ORDER BY id DESC LIMIT 1
        )
    ''')
    rows = c.fetchall()
    conn.close()
    return rows


def get_dashboard_stats():
    conn = get_db_connection()
    c = conn.cursor()
    stats = {}
    c.execute('SELECT COUNT(*) FROM Candidates')
    stats['total_candidates'] = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM JobPositions')
    stats['total_positions'] = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM Results')
    stats['total_results'] = c.fetchone()[0]
    c.execute("SELECT AVG(cf) FROM Results")
    avg_cf = c.fetchone()[0]
    stats['average_cf'] = round(avg_cf, 2) if avg_cf is not None else None
    c.execute("SELECT COUNT(*) FROM Results WHERE recommendation LIKE '%sangat cocok%'")
    stats['recommended_count'] = c.fetchone()[0]
    stats['not_recommended_count'] = stats['total_results'] - stats['recommended_count'] if stats['total_results'] is not None else 0
    c.execute("SELECT COUNT(*) FROM Candidates WHERE job_position_id IS NOT NULL")
    stats['candidates_with_position'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM Candidates WHERE culture_fit = 'yes'")
    stats['culture_fit_yes'] = c.fetchone()[0]
    conn.close()
    return stats

# Fungsi untuk menyimpan data posisi pekerjaan
def save_job_position(title, description, qualifications, required_skills):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO JobPositions (title, description, qualifications, required_skills) VALUES (?, ?, ?, ?)',
              (title, description, qualifications, required_skills))
    conn.commit()
    conn.close()

def save_result(candidate_id, job_position_id, cf, recommendation):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO Results (candidate_id, job_position_id, cf, recommendation)
        VALUES (?, ?, ?, ?)
    ''', (candidate_id, job_position_id, cf, recommendation))
    conn.commit()
    conn.close()


@app.route('/delete_candidate/<int:candidate_id>', methods=['POST'])
def delete_candidate(candidate_id):
    conn = get_db_connection()
    c = conn.cursor()
    # Hapus hasil terkait kandidat terlebih dahulu
    c.execute('DELETE FROM Results WHERE candidate_id = ?', (candidate_id,))
    # Hapus kandidat
    c.execute('DELETE FROM Candidates WHERE id = ?', (candidate_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('data_kandidat'))


@app.route('/delete_job_position/<int:job_position_id>', methods=['POST'])
def delete_job_position(job_position_id):
    conn = get_db_connection()
    c = conn.cursor()
    # Set kandidat yang punya posisi ini menjadi NULL
    c.execute('UPDATE Candidates SET job_position_id = NULL WHERE job_position_id = ?', (job_position_id,))
    # Hapus hasil yang merujuk ke posisi ini
    c.execute('DELETE FROM Results WHERE job_position_id = ?', (job_position_id,))
    # Hapus posisi
    c.execute('DELETE FROM JobPositions WHERE id = ?', (job_position_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('data_posisi'))


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

@app.route('/')
def index():
    # Tampilkan dashboard ringkasan statistik
    stats = get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/data_kandidat')
def data_kandidat():
    candidates = get_candidates()
    return render_template('data_kandidat.html', candidates=candidates)

@app.route('/data_posisi')
def data_posisi():
    job_positions = get_job_positions()
    return render_template('data_posisi.html', job_positions=job_positions)

@app.route('/results')
def results():
    # Ambil hasil seleksi dari database
    results = get_results()  # Pastikan Anda sudah mendefinisikan fungsi get_results() sebelumnya
    return render_template('results.html', results=results)

@app.route('/add_candidate', methods=['GET', 'POST'])
def add_candidate():
    form = CandidateForm()

    # Ambil data posisi pekerjaan untuk dropdown
    form.job_position.choices = [(job['id'], job['title']) for job in get_job_positions()]

    if form.validate_on_submit():
        name = form.name.data
        experience = form.experience.data
        education = form.education.data
        skills = form.skills.data
        culture_fit = form.culture_fit.data
        job_position_id = form.job_position.data  # Ambil job position yang dipilih
        save_candidate(name, experience, education, skills, culture_fit, job_position_id)

        return redirect(url_for('data_kandidat'))
    return render_template('add_candidate.html', form=form)

@app.route('/add_job_position', methods=['GET', 'POST'])
def add_job_position():
    form = JobPositionForm()
    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        qualifications = form.qualifications.data
        required_skills = form.required_skills.data
        save_job_position(title, description, qualifications, required_skills)
        return redirect(url_for('data_posisi'))
    return render_template('add_job_position.html', form=form)

@app.route('/process_selection/<int:candidate_id>/<int:job_position_id>', methods=['GET', 'POST'])
def process_selection(candidate_id, job_position_id):
    # Ambil data kandidat dan posisi pekerjaan
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM Candidates WHERE id = ?', (candidate_id,))
    candidate = c.fetchone()
    # Gunakan job_position_id yang tersimpan di record kandidat (posisi yang dilamar)
    applied_job_id = candidate['job_position_id']
    c.execute('SELECT * FROM JobPositions WHERE id = ?', (applied_job_id,))
    job_position = c.fetchone()
    conn.close()

    # Hitung CF berdasarkan pengalaman, pendidikan, keterampilan, dan budaya
    cf = calculate_cf(candidate['experience'], candidate['education'], candidate['skills'], candidate['culture_fit'], applied_job_id)

    # Tentukan rekomendasi berdasarkan CF
    recommendation = "Kandidat sangat cocok untuk posisi ini." if cf > 2.5 else "Kandidat kurang cocok untuk posisi ini."

    # Simpan hasil seleksi ke dalam database (gunakan posisi yang dilamar kandidat)
    save_result(candidate_id, applied_job_id, cf, recommendation)

    return redirect(url_for('data_kandidat'))

def get_results():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT Candidates.name, Candidates.experience, Candidates.education, Candidates.skills, Candidates.culture_fit,
               JobPositions.title AS position_title, Results.cf, Results.recommendation
        FROM Results
        JOIN Candidates ON Results.candidate_id = Candidates.id
        -- Ambil judul posisi berdasarkan posisi yang tersimpan pada record kandidat
        LEFT JOIN JobPositions ON Candidates.job_position_id = JobPositions.id
        ORDER BY Results.id DESC
    ''')
    results = c.fetchall()
    conn.close()
    return results


if __name__ == "__main__":
    app.run(debug=True)
