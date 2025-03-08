from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; you should restrict this in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# PostgreSQL connection string
DATABASE_URL = "postgresql://rushita_user:xHFJdbYFuaPeiiEsPQ4Yc8JafIHaaagq@dpg-cv4ra4qj1k6c738qjsmg-a/rushita"

# Pydantic Models
class Medicine(BaseModel):
    name: str
    dosage: str
    frequency: str
    note: str = ""

class PrescriptionData(BaseModel):
    patientName: str
    patientAge: str
    patientDescription: str
    currentDate: str
    medicines: List[Medicine]
    sendToValue: str = ""

# Database connection function
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Create tables function
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create prescriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY,
            patientName TEXT NOT NULL,
            patientAge TEXT NOT NULL,
            patientDescription TEXT NOT NULL,
            currentDate TEXT NOT NULL,
            sendToValue TEXT
        )
    """)
    
    # Create medicines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id SERIAL PRIMARY KEY,
            prescription_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            frequency TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# Create tables on startup
create_tables()

@app.get("/prescriptions/{prescription_id}")
async def get_prescription(prescription_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get prescription data
    cursor.execute("SELECT * FROM prescriptions WHERE id = %s", (prescription_id,))
    prescription_row = cursor.fetchone()

    if not prescription_row:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Get medicines for this prescription
    cursor.execute("SELECT * FROM medicines WHERE prescription_id = %s", (prescription_id,))
    medicines_rows = cursor.fetchall()

    medicines = [
        Medicine(
            name=row['name'],
            dosage=row['dosage'],
            frequency=row['frequency'],
            note=row['note']
        )
        for row in medicines_rows
    ]

    prescription = PrescriptionData(
        patientName=prescription_row['patientname'],
        patientAge=prescription_row['patientage'],
        patientDescription=prescription_row['patientdescription'],
        currentDate=prescription_row['currentdate'],
        sendToValue=prescription_row['sendtovalue'],
        medicines=medicines
    )
    
    cursor.close()
    conn.close()
    return prescription

@app.post("/prescriptions/{prescription_id}")
async def update_prescription(prescription_id: int, updated_prescription: PrescriptionData):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if prescription exists
    cursor.execute("SELECT id FROM prescriptions WHERE id = %s", (prescription_id,))
    existing_prescription = cursor.fetchone()
    if not existing_prescription:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Update prescription
    cursor.execute("""
        UPDATE prescriptions SET patientName = %s, patientAge = %s, patientDescription = %s, 
        currentDate = %s, sendToValue = %s WHERE id = %s
    """, (
        updated_prescription.patientName,
        updated_prescription.patientAge,
        updated_prescription.patientDescription,
        updated_prescription.currentDate,
        updated_prescription.sendToValue,
        prescription_id
    ))

    # Delete existing medicines
    cursor.execute("DELETE FROM medicines WHERE prescription_id = %s", (prescription_id,))

    # Insert updated medicines
    for medicine in updated_prescription.medicines:
        cursor.execute("""
            INSERT INTO medicines (prescription_id, name, dosage, frequency, note) VALUES (%s, %s, %s, %s, %s)
        """, (
            prescription_id,
            medicine.name,
            medicine.dosage,
            medicine.frequency,
            medicine.note
        ))

    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Prescription updated"}

@app.post("/store")
async def create_prescription(prescription: PrescriptionData):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert prescription
    cursor.execute("""
        INSERT INTO prescriptions (patientName, patientAge, patientDescription, currentDate, sendToValue) 
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, (
        prescription.patientName,
        prescription.patientAge,
        prescription.patientDescription,
        prescription.currentDate,
        prescription.sendToValue
    ))
    
    # Get the newly created prescription ID
    prescription_id = cursor.fetchone()[0]

    # Insert medicines
    for medicine in prescription.medicines:
        cursor.execute("""
            INSERT INTO medicines (prescription_id, name, dosage, frequency, note) VALUES (%s, %s, %s, %s, %s)
        """, (
            prescription_id,
            medicine.name,
            medicine.dosage,
            medicine.frequency,
            medicine.note
        ))

    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Prescription created with ID: " + str(prescription_id)}
