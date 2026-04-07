# Manual Setup Guide

## One-time setup (do this once ever)

### Step 1 — Database

Open SQL Developer, connect to your Oracle DB, and run these 4 files in order (File → Open → Run):

```
database/01_schema.sql
database/02_triggers.sql
database/03_procedures.sql
database/04_sample_data.sql
```

Close SQL Developer. Done with DB forever.

### Step 2 — Backend config

Go to the `backend` folder, copy `.env.example`, rename it to `.env`, and fill in your Oracle username/password:

```
ORACLE_USER=your_username
ORACLE_PASSWORD=your_password
ORACLE_DSN=localhost:1521/XEPDB1
```

### Step 3 — Install dependencies (once)

```bash
cd backend
pip install -r requirements.txt
```

```bash
cd frontend
npm install
```

---

## Every time you want to run the app

Open **two terminals**:

**Terminal 1 — Backend:**

```bash
cd backend
python app.py
```

Leave it running.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Leave it running.

Open your browser at **http://localhost:3000**.

---

> Oracle is always running in the background as a Windows service — you never touch it again after the first-time setup.
