from app import app, db, bcrypt, User

def reset_database():
    with app.app_context():
        # 1. Zmažeme všetky tabuľky (ekvivalent zmazania súboru, ale bezpečnejší)
        db.drop_all()
        print("   - Staré tabuľky zmazané.")
        
        # 2. Vytvoríme nové tabuľky
        db.create_all()
        print("   - Nové tabuľky vytvorené.")
        
        # 3. (VOLITEĽNÉ) Vytvoríme testovacieho používateľa
        # Aby si sa nemusel stále registrovať
        USER = "admin"
        PASS = "123"
        hashed_password = bcrypt.generate_password_hash(PASS).decode('utf-8')
        test_user = User(username=USER, password=hashed_password)
        
        db.session.add(test_user)
        db.session.commit()
        
        print(f"   - Vytvorený používateľ: '{USER}' / '{PASS}'")

    print("✅ HOTOVO! Databáza je pripravená.")

if __name__ == '__main__':
    print("⏳ Reštartujem databázu...")
    reset_database()