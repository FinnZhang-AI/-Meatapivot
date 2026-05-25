-- Meatapivot Database Initialization Script
-- PostgreSQL 15+

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Users table (for local auth, Keycloak is primary)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    bucket_name VARCHAR(255) DEFAULT 'knowledge-base',
    object_key VARCHAR(512) NOT NULL,
    uploaded_by UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'uploaded',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Decision Flows table
CREATE TABLE IF NOT EXISTS decision_flows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    dag_definition JSONB NOT NULL,
    version INTEGER DEFAULT 1,
    created_by UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'draft',
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Decision Flow Executions table
CREATE TABLE IF NOT EXISTS flow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flow_id UUID REFERENCES decision_flows(id) ON DELETE CASCADE,
    execution_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,
    error_message TEXT,
    logs JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Knowledge Graph Entities table (cached from Neo4j)
CREATE TABLE IF NOT EXISTS kg_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100),
    properties JSONB DEFAULT '{}',
    neo4j_node_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_decision_flows_created_by ON decision_flows(created_by);
CREATE INDEX IF NOT EXISTS idx_decision_flows_status ON decision_flows(status);

CREATE INDEX IF NOT EXISTS idx_flow_executions_flow_id ON flow_executions(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_executions_status ON flow_executions(status);
CREATE INDEX IF NOT EXISTS idx_flow_executions_created_at ON flow_executions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON kg_entities(entity_name);
CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type);

-- Text search index for documents
CREATE INDEX IF NOT EXISTS idx_documents_filename_search ON documents USING gin(to_tsvector('english', original_name));

-- Insert default tenant (required for foreign key constraint)
INSERT INTO tenants (id, name, description, is_active)
VALUES ('00000000-0000-0000-0000-000000000000'::uuid, 'Default Tenant', 'System default tenant', true)
ON CONFLICT (id) DO NOTHING;

-- Insert default admin user (password: admin123 — change immediately in production)
-- bcrypt hash for 'admin123'
INSERT INTO users (username, email, full_name, hashed_password, role, tenant_id) 
VALUES ('admin', 'admin@localhost', 'System Administrator', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I1K', 'admin', '00000000-0000-0000-0000-000000000000')
ON CONFLICT (username) DO NOTHING;

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_decision_flows_updated_at BEFORE UPDATE ON decision_flows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_kg_entities_updated_at BEFORE UPDATE ON kg_entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Ontology compile version tracking
CREATE TABLE IF NOT EXISTS ontology_current_version (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    log_id UUID REFERENCES ontology_compile_logs(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add missing columns to ontology_compile_logs (if table already exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ontology_compile_logs') THEN
        ALTER TABLE ontology_compile_logs 
            ADD COLUMN IF NOT EXISTS version VARCHAR(20),
            ADD COLUMN IF NOT EXISTS parent_version VARCHAR(20),
            ADD COLUMN IF NOT EXISTS affected_types JSONB DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS diff_snapshot JSONB NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS neo4j_stmts JSONB DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS error_detail TEXT,
            ADD COLUMN IF NOT EXISTS rolled_back_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS rolled_back_by UUID REFERENCES users(id);
    END IF;
END $$;

COMMENT ON TABLE users IS 'User accounts for the platform';
COMMENT ON TABLE documents IS 'Uploaded documents stored in MinIO';
COMMENT ON TABLE decision_flows IS 'Decision flow definitions (DAG)';
COMMENT ON TABLE flow_executions IS 'Execution history of decision flows';
COMMENT ON TABLE kg_entities IS 'Cached knowledge graph entities from Neo4j';
COMMENT ON TABLE ontology_current_version IS 'Current active Ontology version per tenant';