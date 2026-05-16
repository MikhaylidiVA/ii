-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create enum types
CREATE TYPE issue_priority AS ENUM ('CRITICAL', 'IMPORTANT', 'RECOMMENDATION');
CREATE TYPE issue_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'RESOLVED');
CREATE TYPE file_type AS ENUM ('PDF', 'DWG', 'DXF');
CREATE TYPE processing_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Files table
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    file_type file_type NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(500),
    processing_status processing_status DEFAULT 'PENDING',
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Norm documents table (regulatory base)
CREATE TABLE IF NOT EXISTS norm_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_name VARCHAR(255) NOT NULL,
    doc_type VARCHAR(50),
    doc_number VARCHAR(100),
    approval_date DATE,
    effective_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    content_hash VARCHAR(64),
    s3_key VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Norm sections/chunks for RAG
CREATE TABLE IF NOT EXISTS norm_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES norm_documents(id) ON DELETE CASCADE,
    section_number VARCHAR(100),
    section_title VARCHAR(500),
    content TEXT NOT NULL,
    parent_section_id UUID REFERENCES norm_sections(id),
    level INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Vector embeddings for norm sections (managed by Qdrant, reference here)
CREATE TABLE IF NOT EXISTS norm_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES norm_sections(id) ON DELETE CASCADE,
    qdrant_point_id UUID NOT NULL,
    model_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Issues (findings) table
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_id UUID REFERENCES files(id) ON DELETE SET NULL,
    priority issue_priority NOT NULL,
    status issue_status DEFAULT 'PENDING',
    category VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT,
    confidence_score REAL DEFAULT 0.0,
    
    -- Reference to regulation
    regulation_doc_id UUID REFERENCES norm_documents(id),
    regulation_section VARCHAR(100),
    regulation_text TEXT,
    
    -- Location data (GeoJSON)
    location_geojson JSONB,
    bbox JSONB,
    coordinate_system VARCHAR(50) DEFAULT 'WCS',
    
    -- Review data
    reviewed_by UUID REFERENCES users(id),
    review_comment TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Processing tasks queue
CREATE TABLE IF NOT EXISTS processing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES files(id) ON DELETE CASCADE,
    task_type VARCHAR(100) NOT NULL,
    celery_task_id VARCHAR(255),
    status processing_status DEFAULT 'PENDING',
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    result JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_files_project_id ON files(project_id);
CREATE INDEX idx_files_processing_status ON files(processing_status);
CREATE INDEX idx_issues_project_id ON issues(project_id);
CREATE INDEX idx_issues_priority ON issues(priority);
CREATE INDEX idx_issues_status ON issues(status);
CREATE INDEX idx_issues_category ON issues(category);
CREATE INDEX idx_norm_sections_document_id ON norm_sections(document_id);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- GIN indexes for JSONB
CREATE INDEX idx_files_metadata ON files USING GIN(metadata);
CREATE INDEX idx_issues_location ON issues USING GIN(location_geojson);
CREATE INDEX idx_norm_sections_content ON norm_sections USING GIN(to_tsvector('russian', content));

-- Spatial index for geometry queries (if using PostGIS geometry type)
-- CREATE INDEX idx_issues_location_geom ON issues USING GIST(ST_GeomFromGeoJSON(location_geojson));

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_norm_documents_updated_at BEFORE UPDATE ON norm_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_issues_updated_at BEFORE UPDATE ON issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin user (password: admin123, change in production!)
INSERT INTO users (email, hashed_password, full_name, role) VALUES
('admin@autonormcheck.ru', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu', 'Administrator', 'admin')
ON CONFLICT (email) DO NOTHING;
