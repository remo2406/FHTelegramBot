import sqlite3
import pandas as pd

def conexao():
    conn = sqlite3.connect('dbautorizados.db')
    c = conn.cursor()
    return conn, c

def adicionarinfodb(user_id):
    conn = conexao()[0]
    c = conexao()[1]

    c.execute(f'''
              INSERT INTO autorizados (user_id, autorizado)
                VALUES
                ({user_id},1)
             ''')
    conn.commit()
    c.close()
    return

def alterarinfodb(user_id):
    conn = conexao()[0]
    c = conexao()[1]

    try:
        c.execute(f'''
                UPDATE autorizados
                SET autorizado = 0
                WHERE user_id = {user_id}
                ''')
        conn.commit()
        c.close()
        return 'Sucesso'
    except Exception as e:
        c.close()
        return e
   
    
def retornadadosdb():
    conn = conexao()[0]
    c = conexao()[1]

    c.execute('''
            SELECT * FROM autorizados
            ''')

    df = pd.DataFrame(c.fetchall(), columns=['user_id','autorizado'])
    c.close()
    return df