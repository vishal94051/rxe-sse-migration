import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def create_tables(engine):
    print("\n--- Creating RxE Source Tables ---")
    with engine.connect() as conn:
        # Extract metadata table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS extract_metadata (
                extract_id      VARCHAR(50) PRIMARY KEY,
                extract_name    VARCHAR(100),
                source_system   VARCHAR(50),
                extract_type    VARCHAR(50),
                status          VARCHAR(20),
                created_date    TIMESTAMP DEFAULT NOW(),
                record_count    INTEGER,
                file_format     VARCHAR(20)
            )
        """))

        # Field mapping table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS field_mappings (
                mapping_id      SERIAL PRIMARY KEY,
                extract_id      VARCHAR(50) REFERENCES extract_metadata(extract_id),
                source_field    VARCHAR(100),
                target_field    VARCHAR(100),
                data_type       VARCHAR(50),
                is_required     BOOLEAN DEFAULT TRUE,
                transformation  VARCHAR(200)
            )
        """))

        # Business rules table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS business_rules (
                rule_id         SERIAL PRIMARY KEY,
                extract_id      VARCHAR(50) REFERENCES extract_metadata(extract_id),
                rule_name       VARCHAR(100),
                rule_type       VARCHAR(50),
                rule_definition TEXT,
                is_active       BOOLEAN DEFAULT TRUE
            )
        """))

        conn.commit()
        print("✅ Tables created successfully!")

def seed_data(engine):
    print("\n--- Seeding Sample RxE Data ---")
    with engine.connect() as conn:

        # Sample extracts
        conn.execute(text("""
            INSERT INTO extract_metadata 
                (extract_id, extract_name, source_system, extract_type, status, record_count, file_format)
            VALUES
                ('EXT001', 'Patient Demographics', 'RxE', 'CLINICAL', 'ACTIVE', 15000, 'JSON'),
                ('EXT002', 'Prescription History', 'RxE', 'PHARMACY', 'ACTIVE', 45000, 'JSON'),
                ('EXT003', 'Insurance Details',   'RxE', 'FINANCIAL', 'ACTIVE', 12000, 'JSON'),
                ('EXT004', 'Lab Results',         'RxE', 'CLINICAL', 'PENDING', 8000,  'JSON')
            ON CONFLICT (extract_id) DO NOTHING
        """))

        # Sample field mappings
        conn.execute(text("""
            INSERT INTO field_mappings 
                (extract_id, source_field, target_field, data_type, is_required, transformation)
            VALUES
                ('EXT001', 'pat_id',        'patientId',       'STRING',  TRUE,  'DIRECT'),
                ('EXT001', 'pat_fname',     'firstName',       'STRING',  TRUE,  'UPPERCASE'),
                ('EXT001', 'pat_lname',     'lastName',        'STRING',  TRUE,  'UPPERCASE'),
                ('EXT001', 'pat_dob',       'dateOfBirth',     'DATE',    TRUE,  'FORMAT:YYYY-MM-DD'),
                ('EXT001', 'pat_gender',    'gender',          'STRING',  FALSE, 'LOOKUP:GENDER_MAP'),
                ('EXT002', 'rx_id',         'prescriptionId',  'STRING',  TRUE,  'DIRECT'),
                ('EXT002', 'rx_drug_code',  'drugCode',        'STRING',  TRUE,  'DIRECT'),
                ('EXT002', 'rx_date',       'prescribedDate',  'DATE',    TRUE,  'FORMAT:YYYY-MM-DD'),
                ('EXT002', 'rx_qty',        'quantity',        'INTEGER', TRUE,  'DIRECT'),
                ('EXT003', 'ins_id',        'insuranceId',     'STRING',  TRUE,  'DIRECT'),
                ('EXT003', 'ins_provider',  'providerName',    'STRING',  TRUE,  'UPPERCASE'),
                ('EXT003', 'ins_plan_code', 'planCode',        'STRING',  TRUE,  'DIRECT')
            ON CONFLICT DO NOTHING
        """))

        # Sample business rules
        conn.execute(text("""
            INSERT INTO business_rules 
                (extract_id, rule_name, rule_type, rule_definition, is_active)
            VALUES
                ('EXT001', 'Valid DOB',         'VALIDATION', 'dateOfBirth must be before today',           TRUE),
                ('EXT001', 'Required Fields',   'VALIDATION', 'patientId, firstName, lastName are required', TRUE),
                ('EXT002', 'Valid Quantity',     'VALIDATION', 'quantity must be greater than 0',            TRUE),
                ('EXT002', 'Active Drug Code',  'LOOKUP',     'drugCode must exist in drug_master table',    TRUE),
                ('EXT003', 'Valid Insurance',   'VALIDATION', 'insuranceId must be alphanumeric',            TRUE)
            ON CONFLICT DO NOTHING
        """))

        conn.commit()
        print("✅ Sample data seeded successfully!")

def verify_data(engine):
    print("\n--- Verifying Seeded Data ---")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM extract_metadata"))
        print(f"   Extract metadata rows : {result.fetchone()[0]}")

        result = conn.execute(text("SELECT COUNT(*) FROM field_mappings"))
        print(f"   Field mapping rows    : {result.fetchone()[0]}")

        result = conn.execute(text("SELECT COUNT(*) FROM business_rules"))
        print(f"   Business rule rows    : {result.fetchone()[0]}")

if __name__ == "__main__":
    engine = create_engine(os.getenv("POSTGRES_URL"))
    create_tables(engine)
    seed_data(engine)
    verify_data(engine)
    print("\n✅ RxE source database is ready!")