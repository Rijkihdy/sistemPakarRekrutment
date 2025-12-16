# import sqlite3

# # Membuat koneksi ke database
# conn = sqlite3.connect('recruitment_system.db')
# c = conn.cursor()

# # Tabel untuk kandidat
# c.execute('''
# CREATE TABLE IF NOT EXISTS Candidates (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT,
#     experience TEXT,
#     education TEXT,
#     skills TEXT,
#     culture_fit TEXT
# )
# ''')

# # Tabel untuk posisi pekerjaan
# c.execute('''
# CREATE TABLE IF NOT EXISTS JobPositions (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     title TEXT,
#     description TEXT,
#     qualifications TEXT,
#     required_skills TEXT
# )
# ''')

# # Tabel untuk aturan seleksi (Rules)
# c.execute('''
# CREATE TABLE IF NOT EXISTS Rules (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     criteria TEXT,
#     value REAL
# )
# ''')

# # Tabel untuk hasil seleksi
# c.execute('''
# CREATE TABLE IF NOT EXISTS Results (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     candidate_id INTEGER,
#     job_position_id INTEGER,
#     cf REAL,
#     recommendation TEXT,
#     FOREIGN KEY(candidate_id) REFERENCES Candidates(id),
#     FOREIGN KEY(job_position_id) REFERENCES JobPositions(id)
# )
# ''')

# conn.commit()
# conn.close()

# print("Database and tables created successfully.")

import sqlite3

# Koneksi ke database
conn = sqlite3.connect('recruitment_system.db')
c = conn.cursor()

# Menambah kolom job_position_id ke dalam tabel Candidates
c.execute('ALTER TABLE Candidates ADD COLUMN owner TEXT;')

# Commit perubahan dan tutup koneksi
conn.commit()
conn.close()

print("Kolom owner berhasil ditambahkan ke tabel Candidates.")
