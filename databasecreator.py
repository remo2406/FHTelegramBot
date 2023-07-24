import sqlite3

conn = sqlite3.connect('dbautorizados.db')
c = conn.cursor()

c.execute('''
          CREATE TABLE autorizados (
          id INTEGER PRIMARY KEY,
          autorizado BOOL
          )''')

conn.commit()
c.close()