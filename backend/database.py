import os
import json
import mysql.connector

# Database connection config. Reads from environment variables with fallback defaults for local development
DB_CONFIG = {
    "host": os.getenv("db_host"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password"),
    "database": os.getenv("db_name"),
    "use_pure": True,
}

# Open and return a new MySQL connection using the config above
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# FastAPI dependency that yields a database connection and closes it after the request is done
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

# Initialize all database tables on startup. Safe to call repeatedly — uses CREATE TABLE IF NOT EXISTS so existing tables are never recreated or overwritten
def init_db():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Column mappings table. Stores confirmed AI or manual mapping per client per file type.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS column_mappings (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            client_id       VARCHAR(255) NOT NULL,
            file_type       VARCHAR(100) NOT NULL DEFAULT 'general',
            original_column VARCHAR(255) NOT NULL,
            mapped_to       VARCHAR(255) NOT NULL,
            field_type      VARCHAR(100) NOT NULL DEFAULT 'unknown',
            reviewed_unknown TINYINT(1) NOT NULL DEFAULT 0,
            required        TINYINT(1) NOT NULL DEFAULT 1,
            confirmed_by    VARCHAR(255),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_column_mapping (client_id, file_type, original_column)
        )
    """)
    cursor.execute("SELECT COUNT(*) AS count FROM information_schema.columns WHERE table_schema = %s AND table_name = 'column_mappings' AND column_name = 'reviewed_unknown'", (DB_CONFIG["database"],))
    if cursor.fetchone()["count"] == 0:
        cursor.execute("ALTER TABLE column_mappings ADD COLUMN reviewed_unknown TINYINT(1) NOT NULL DEFAULT 0")
    cursor.execute("SELECT COUNT(*) AS count FROM information_schema.columns WHERE table_schema = %s AND table_name = 'column_mappings' AND column_name = 'required'", (DB_CONFIG["database"],))
    if cursor.fetchone()["count"] == 0:
        cursor.execute("ALTER TABLE column_mappings ADD COLUMN required TINYINT(1) NOT NULL DEFAULT 1")

    # Clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            contact_person VARCHAR(255),
            email VARCHAR(255),
            phone VARCHAR(50),
            industry VARCHAR(255),
            address VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Active',
            kra_pin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Schema fingerprints table. file_type now stores the REAL file_type category
    # (e.g. "accounts_payable"), not a file extension — saved from /detect-columns,
    # which is the only place the real category is known.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_fingerprints (
            id INT AUTO_INCREMENT PRIMARY KEY,
            client_id VARCHAR(255) NOT NULL,
            fingerprint VARCHAR(255) NOT NULL,
            file_type VARCHAR(100) NOT NULL DEFAULT 'general',
            columns_snapshot TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_fingerprint (client_id, fingerprint, file_type)
        )
    """)

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(50),
            role VARCHAR(50) NOT NULL,
            assigned_client_id INT,
            status VARCHAR(50) DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Password resets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            reset_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            token VARCHAR(255) NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Engagements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engagements (
            engagement_id INT AUTO_INCREMENT PRIMARY KEY,
            client_id INT NOT NULL,
            engagement_name VARCHAR(255) NOT NULL,
            financial_year VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'Planning',
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Audit sections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_sections (
            section_id INT AUTO_INCREMENT PRIMARY KEY,
            engagement_id INT NOT NULL,
            section_name VARCHAR(255) NOT NULL,
            status VARCHAR(50) DEFAULT 'Pending',
            assigned_to INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Engagement team table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engagement_team (
            team_id INT AUTO_INCREMENT PRIMARY KEY,
            engagement_id INT NOT NULL,
            user_id INT NOT NULL,
            role VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_engagement_team (engagement_id, user_id)
        )
    """)

    # Submissions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id INT AUTO_INCREMENT PRIMARY KEY,
            engagement_id INT NOT NULL,
            section_id INT NOT NULL,
            submitted_by INT NOT NULL,
            status VARCHAR(50) DEFAULT 'Draft',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Notifications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(100) DEFAULT 'engagement_alert',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Uploads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            file_id     VARCHAR(255) NOT NULL UNIQUE,
            client_id   VARCHAR(255) NOT NULL,
            filename    VARCHAR(255) NOT NULL,
            file_name   VARCHAR(255),
            file_type   VARCHAR(100) NOT NULL,
            file_path   VARCHAR(500),
            `rows`      INT,
            status      VARCHAR(50) DEFAULT 'uploaded',
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT COUNT(*) AS count FROM information_schema.columns WHERE table_schema = %s AND table_name = 'uploads' AND column_name = 'file_name'", (DB_CONFIG["database"],))
    if cursor.fetchone()["count"] == 0:
        cursor.execute("ALTER TABLE uploads ADD COLUMN file_name VARCHAR(255) NULL")
    cursor.execute("SELECT COUNT(*) AS count FROM information_schema.columns WHERE table_schema = %s AND table_name = 'uploads' AND column_name = 'file_path'", (DB_CONFIG["database"],))
    if cursor.fetchone()["count"] == 0:
        cursor.execute("ALTER TABLE uploads ADD COLUMN file_path VARCHAR(500) NULL")
    cursor.execute("SELECT COUNT(*) AS count FROM information_schema.columns WHERE table_schema = %s AND table_name = 'uploads' AND column_name = 'upload_date'", (DB_CONFIG["database"],))
    if cursor.fetchone()["count"] == 0:
        cursor.execute("ALTER TABLE uploads ADD COLUMN upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    # Auditor acknowledgments for issues that are valid as-is
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleaning_acknowledgments (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            issue_id        VARCHAR(64) NOT NULL UNIQUE,
            file_id         VARCHAR(255) NOT NULL,
            client_id       VARCHAR(255) NOT NULL,
            file_type       VARCHAR(100) NOT NULL,
            row_index       VARCHAR(50),
            excel_row       VARCHAR(50),
            column_name     VARCHAR(255),
            original_value  TEXT,
            issue_message   TEXT,
            acknowledged_by VARCHAR(255),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Inline corrections (also used for row/column deletion markers from the Excel re-upload flow)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleaning_corrections (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            file_id        VARCHAR(255) NOT NULL,
            client_id      VARCHAR(255) NOT NULL,
            file_type      VARCHAR(100) NOT NULL,
            row_index      INT NOT NULL,
            column_name    VARCHAR(255) NOT NULL,
            original_value TEXT,
            corrected_value TEXT,
            corrected_by   VARCHAR(255),
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_cleaning_correction (file_id(64), client_id(64), file_type(64), row_index, column_name(191))
        )
    """)

    # Cleaning snapshots table. Stores the cleaned data exactly as it looked when the
    # Excel was downloaded, so a later re-uploaded corrected file can be compared
    # against the exact data the auditor started editing from.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleaning_snapshots (
            file_id       VARCHAR(255) NOT NULL,
            client_id     VARCHAR(255) NOT NULL,
            file_type     VARCHAR(100) NOT NULL,
            snapshot_data LONGTEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (file_id, client_id, file_type)
        )
    """)

    conn.commit()
    conn.close()


# Save a confirmed column mapping for a client to the database.
def save_mapping(client_id: str, file_type: str, mapping: dict, confirmed_by: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM column_mappings WHERE client_id = %s AND file_type = %s",
        (client_id, file_type)
    )
    for original_column, info in mapping.items():
        if isinstance(info, dict):
            mapped_to  = str(info.get("mapped_to", "unknown"))
            field_type = str(info.get("field_type", "unknown"))
            reviewed_unknown = 1 if info.get("reviewed_unknown") else 0
            required = 1 if info.get("required", True) else 0
        else:
            mapped_to  = str(info)
            field_type = "unknown"
            reviewed_unknown = 0
            required = 1
        cursor.execute("""
            INSERT INTO column_mappings
                (client_id, file_type, original_column, mapped_to, field_type, reviewed_unknown, required, confirmed_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                mapped_to        = VALUES(mapped_to),
                field_type       = VALUES(field_type),
                reviewed_unknown = VALUES(reviewed_unknown),
                required         = VALUES(required),
                confirmed_by     = VALUES(confirmed_by),
                updated_at       = CURRENT_TIMESTAMP
        """, (client_id, file_type, original_column, mapped_to, field_type, reviewed_unknown, required, confirmed_by))
    conn.commit()
    conn.close()


# Save a schema fingerprint, keyed by client + fingerprint + REAL file_type category.
def save_fingerprint(client_id: str, fingerprint: str, file_type: str, columns: list):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO schema_fingerprints
            (client_id, fingerprint, file_type, columns_snapshot)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE id = id
    """, (
        client_id,
        fingerprint,
        file_type,
        json.dumps(columns)
    ))
    conn.commit()
    conn.close()


def get_fingerprint(client_id: str, fingerprint: str, file_type: str = "general") -> bool:
    """
    Check if a schema fingerprint already exists for a client AND file type.
    Filtering by file_type prevents two different file types that happen to share
    the same column-name structure from incorrectly matching each other's cache entry.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM schema_fingerprints
        WHERE client_id = %s AND fingerprint = %s AND file_type = %s
    """, (client_id, fingerprint, file_type))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_mapping(client_id: str, file_type: str = "general") -> dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT original_column, mapped_to, field_type, reviewed_unknown, required
        FROM column_mappings
        WHERE client_id = %s AND file_type = %s
    """, (client_id, file_type))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return {}
    return {
        row["original_column"]: {
            "mapped_to":       row["mapped_to"],
            "field_type":      row["field_type"],
            "reviewed_unknown": bool(row.get("reviewed_unknown", 0)),
            "required":        bool(row.get("required", 1))
        }
        for row in rows
    }


def save_upload(file_id: str, client_id: str, filename: str, file_type: str, rows: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO uploads (file_id, client_id, filename, file_type, `rows`) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE file_id = file_id",
        (file_id, client_id, filename, file_type, rows)
    )
    conn.commit()
    conn.close()


def get_uploads(client_id: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.*, c.company_name
        FROM uploads u
        LEFT JOIN clients c ON u.client_id = c.client_id
        WHERE u.client_id = %s
        ORDER BY u.upload_time DESC
    """, (client_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_cleaning_acknowledgment(
    issue_id: str,
    file_id: str,
    client_id: str,
    file_type: str,
    issue: dict,
    acknowledged_by: str = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cleaning_acknowledgments
            (issue_id, file_id, client_id, file_type, row_index, excel_row, column_name,
             original_value, issue_message, acknowledged_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            acknowledged_by = VALUES(acknowledged_by),
            created_at = CURRENT_TIMESTAMP
    """, (
        issue_id,
        file_id,
        client_id,
        file_type,
        str(issue.get("row_index", "")),
        str(issue.get("row", "")),
        issue.get("column"),
        str(issue.get("original_value", "")),
        issue.get("issue"),
        acknowledged_by,
    ))
    conn.commit()
    conn.close()


def get_acknowledged_issue_ids(file_id: str, client_id: str, file_type: str) -> set:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT issue_id FROM cleaning_acknowledgments
        WHERE file_id = %s AND client_id = %s AND file_type = %s
    """, (file_id, client_id, file_type))
    rows = cursor.fetchall()
    conn.close()
    return {row["issue_id"] for row in rows}


def save_cleaning_corrections(
    file_id: str,
    client_id: str,
    file_type: str,
    corrections: list,
    corrected_by: str = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    for correction in corrections:
        cursor.execute("""
            INSERT INTO cleaning_corrections
                (file_id, client_id, file_type, row_index, column_name, original_value,
                 corrected_value, corrected_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                original_value = VALUES(original_value),
                corrected_value = VALUES(corrected_value),
                corrected_by = VALUES(corrected_by),
                updated_at = CURRENT_TIMESTAMP
        """, (
            file_id,
            client_id,
            file_type,
            int(correction["row_index"]),
            correction["column"],
            str(correction.get("original_value", "")),
            str(correction.get("corrected_value", "")),
            corrected_by,
        ))
    conn.commit()
    conn.close()


def get_cleaning_corrections(file_id: str, client_id: str, file_type: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT row_index, column_name, corrected_value
        FROM cleaning_corrections
        WHERE file_id = %s AND client_id = %s AND file_type = %s
    """, (file_id, client_id, file_type))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_cleaning_snapshot(file_id: str, client_id: str, file_type: str, cleaned_df):
    """
    Save the cleaned data exactly as it looked at the moment an Excel export was generated.
    This snapshot is what a later re-uploaded corrected file gets compared against.
    Overwrites any previous snapshot for this file_id + client_id + file_type.
    """
    conn = get_connection()
    cursor = conn.cursor()
    snapshot_json = cleaned_df.reset_index().rename(columns={"index": "_row_index"}).to_json(orient="records")
    cursor.execute("""
        INSERT INTO cleaning_snapshots (file_id, client_id, file_type, snapshot_data)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            snapshot_data = VALUES(snapshot_data),
            created_at = CURRENT_TIMESTAMP
    """, (file_id, client_id, file_type, snapshot_json))
    conn.commit()
    conn.close()


def get_cleaning_snapshot(file_id: str, client_id: str, file_type: str):
    """
    Retrieve the saved cleaned-data snapshot for comparison against a re-uploaded corrected file.
    Returns a list of row dicts, or None if no snapshot was ever saved.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT snapshot_data FROM cleaning_snapshots
        WHERE file_id = %s AND client_id = %s AND file_type = %s
    """, (file_id, client_id, file_type))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["snapshot_data"])