-- Enterprise Agent Platform MySQL schema (phase 2)
-- MySQL 8.0+

CREATE TABLE IF NOT EXISTS user_credentials (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  username VARCHAR(128) NOT NULL,
  password_hash TEXT NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'employee',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_credentials (tenant_id, username),
  UNIQUE KEY uk_user_credentials_user_id (tenant_id, user_id),
  KEY idx_user_role_status (tenant_id, role, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  token_id VARCHAR(64) NOT NULL UNIQUE,
  tenant_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  refresh_token_hash TEXT NOT NULL,
  expires_at DATETIME NOT NULL,
  revoked TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_refresh_lookup (tenant_id, user_id, session_id),
  KEY idx_refresh_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS task_queue_status (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL UNIQUE,
  tenant_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  task_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  trace_id VARCHAR(64) DEFAULT NULL,
  request_json JSON NOT NULL,
  result_json JSON NULL,
  error_message TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_task_queue_status (tenant_id, status),
  KEY idx_task_queue_trace (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  event_id VARCHAR(64) NOT NULL UNIQUE,
  event_type VARCHAR(64) NOT NULL,
  trace_id VARCHAR(64) DEFAULT NULL,
  tenant_id VARCHAR(64) DEFAULT NULL,
  payload_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_audit_event_trace (trace_id),
  KEY idx_audit_event_type (event_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  trace_id VARCHAR(64) NOT NULL,
  is_correct TINYINT(1) NOT NULL,
  score DECIMAL(5,4) NOT NULL,
  user_edit TEXT NULL,
  tags_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_feedback_trace (trace_id),
  KEY idx_feedback_tenant_time (tenant_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  source_id VARCHAR(128) NOT NULL,
  chunk_id VARCHAR(64) NOT NULL,
  content MEDIUMTEXT NOT NULL,
  metadata_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chunk (tenant_id, source_id, chunk_id),
  KEY idx_chunk_source (tenant_id, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
