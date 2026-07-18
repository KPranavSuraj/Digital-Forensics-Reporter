-- ══════════════════════════════════════════════════════════════════════════
-- AUTOPSY SIM — MySQL Database Setup
-- Run this ONCE in MySQL Workbench or CLI before starting the server
--
--   mysql -u root -p < SETUP_MYSQL.sql
-- ══════════════════════════════════════════════════════════════════════════

-- 1. Create database
CREATE DATABASE IF NOT EXISTS dfr_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE dfr_db;

-- 2. Create dedicated user
CREATE USER IF NOT EXISTS 'dfr_user'@'localhost'
    IDENTIFIED BY 'dfr_password';

GRANT ALL PRIVILEGES ON dfr_db.* TO 'dfr_user'@'localhost';
FLUSH PRIVILEGES;

-- 3. Tables are created automatically by init_db() on first server start
--    but you can pre-create them here if you prefer:

CREATE TABLE IF NOT EXISTS users (
    username      VARCHAR(50)  PRIMARY KEY,
    password_hash VARCHAR(250) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'viewer',
    label         VARCHAR(100),
    allowed_cases JSON,
    can_upload    TINYINT(1)   DEFAULT 0,
    can_query     TINYINT(1)   DEFAULT 0,
    can_report    TINYINT(1)   DEFAULT 1,
    default_case  JSON,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cases (
    id            VARCHAR(36)  PRIMARY KEY,
    status        VARCHAR(20)  DEFAULT 'uploaded',
    file_path     TEXT,
    filename      VARCHAR(255),
    case_name     VARCHAR(200),
    analyst_name  VARCHAR(100),
    case_number   VARCHAR(50),
    department    VARCHAR(100),
    sha256        VARCHAR(70),
    is_disk_image TINYINT(1)   DEFAULT 0,
    analysis_mode VARCHAR(20)  DEFAULT 'detailed',
    report_path   TEXT,
    error_message TEXT,
    pipeline_step VARCHAR(50),
    session_token VARCHAR(120),
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token         VARCHAR(120) PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL,
    role          VARCHAR(20),
    label         VARCHAR(100),
    allowed_cases JSON,
    can_upload    TINYINT(1),
    can_query     TINYINT(1),
    can_report    TINYINT(1),
    default_case  JSON,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME     DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME
);

CREATE TABLE IF NOT EXISTS login_attempts (
    ip_address    VARCHAR(45)  PRIMARY KEY,
    attempt_count INT          DEFAULT 0,
    locked_until  DATETIME     NULL,
    last_attempt  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    case_id       VARCHAR(36)  NULL,
    username      VARCHAR(50),
    action        VARCHAR(100),
    detail        TEXT,
    ip_address    VARCHAR(45),
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_case  (case_id),
    INDEX idx_user  (username),
    INDEX idx_time  (created_at)
);

CREATE TABLE IF NOT EXISTS csrf_tokens (
    token         VARCHAR(120) PRIMARY KEY,
    expires_at    DATETIME     NOT NULL,
    INDEX idx_exp (expires_at)
);

SELECT 'Database setup complete. Start the server — init_db() will seed default users.' AS status;
