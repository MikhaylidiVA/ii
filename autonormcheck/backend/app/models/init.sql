-- Инициализация базы данных AutoNormCheck
-- Создание расширений и таблиц

-- Включение PostGIS для работы с геометрией
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Для нечеткого поиска текста

-- Создание enum типов (если не созданы через SQLAlchemy)
DO $$ BEGIN
    CREATE TYPE issue_priority AS ENUM ('CRITICAL', 'IMPORTANT', 'RECOMMENDATION');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE issue_category AS ENUM (
        'ROAD_SAFETY', 'ACCESSIBILITY', 'LANDSCAPING', 'PARKING',
        'DRAINAGE', 'LIGHTING', 'SIGNAGE', 'DIMENSIONS',
        'CONFLICTS', 'MISSING_ELEMENTS'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE review_status AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED', 'RESOLVED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Индексы для ускорения поиска
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_file_type ON project_files(file_type);
CREATE INDEX IF NOT EXISTS idx_issues_project_id ON issues(project_id);
CREATE INDEX IF NOT EXISTS idx_issues_priority ON issues(priority);
CREATE INDEX IF NOT EXISTS idx_issues_category ON issues(category);
CREATE INDEX IF NOT EXISTS idx_issues_review_status ON issues(review_status);
CREATE INDEX IF NOT EXISTS idx_issues_confidence ON issues(confidence_score DESC);

-- Пространственный индекс для геометрии
CREATE INDEX IF NOT EXISTS idx_issues_location_geometry 
ON issues USING GIST (location_geometry);

-- Индексы для нормативных документов
CREATE INDEX IF NOT EXISTS idx_norm_documents_document_id ON norm_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_norm_documents_type ON norm_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_norm_documents_status ON norm_documents(status);
CREATE INDEX IF NOT EXISTS idx_norm_chunks_document_id ON norm_chunks(document_id);

-- Полнотекстовый поиск по содержанию норм
ALTER TABLE norm_chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector;

CREATE OR REPLACE FUNCTION update_content_tsv() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector('russian', COALESCE(NEW.content, '') || ' ' || COALESCE(NEW.section_title, ''));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_content_tsv_trigger ON norm_chunks;
CREATE TRIGGER update_content_tsv_trigger
    BEFORE INSERT OR UPDATE ON norm_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_content_tsv();

-- Заполнение существующих записей
UPDATE norm_chunks SET content_tsv = to_tsvector('russian', COALESCE(content, '') || ' ' || COALESCE(section_title, ''));

-- Индекс для полнотекстового поиска
CREATE INDEX IF NOT EXISTS idx_norm_chunks_content_tsv ON norm_chunks USING GIN(content_tsv);

-- Представление для статистики проектов
CREATE OR REPLACE VIEW project_statistics AS
SELECT 
    p.id as project_id,
    p.name as project_name,
    p.status as project_status,
    COUNT(DISTINCT f.id) as total_files,
    COUNT(DISTINCT i.id) as total_issues,
    COUNT(DISTINCT CASE WHEN i.priority = 'CRITICAL' THEN i.id END) as critical_issues,
    COUNT(DISTINCT CASE WHEN i.priority = 'IMPORTANT' THEN i.id END) as important_issues,
    COUNT(DISTINCT CASE WHEN i.priority = 'RECOMMENDATION' THEN i.id END) as recommendation_issues,
    COUNT(DISTINCT CASE WHEN i.review_status = 'CONFIRMED' THEN i.id END) as confirmed_issues,
    COUNT(DISTINCT CASE WHEN i.review_status = 'REJECTED' THEN i.id END) as rejected_issues,
    AVG(i.confidence_score) as avg_confidence_score,
    p.processing_completed_at,
    p.created_at
FROM projects p
LEFT JOIN project_files f ON p.id = f.project_id
LEFT JOIN issues i ON p.id = i.project_id
GROUP BY p.id, p.name, p.status, p.processing_completed_at, p.created_at;

-- Функция для очистки старых проектов (вызывается по расписанию)
CREATE OR REPLACE FUNCTION cleanup_old_projects(days_to_keep INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    cutoff_date TIMESTAMP;
BEGIN
    cutoff_date := NOW() - INTERVAL '1 day' * days_to_keep;
    
    -- Подсчет удаляемых проектов
    SELECT COUNT(*) INTO deleted_count
    FROM projects
    WHERE created_at < cutoff_date;
    
    -- Удаление каскадно (благодаря foreign keys)
    DELETE FROM projects
    WHERE created_at < cutoff_date;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применение триггера к таблицам
DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_issues_updated_at ON issues;
CREATE TRIGGER update_issues_updated_at
    BEFORE UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Начальные данные для тестирования (опционально)
-- INSERT INTO norm_documents (document_id, document_name, document_type, year, status)
-- VALUES 
--     ('gost_r_52289_2014', 'ГОСТ Р 52289-2014 Технические средства организации дорожного движения', 'ГОСТ', 2014, 'active'),
--     ('gost_33150_2019', 'ГОСТ 33150-2019 Дороги автомобильные общего пользования', 'ГОСТ', 2019, 'active'),
--     ('sp_34_13330_2021', 'СП 34.13330.2021 Автомобильные дороги', 'СП', 2021, 'active');

COMMENT ON TABLE projects IS 'Проекты с загруженной документацией';
COMMENT ON TABLE project_files IS 'Загруженные файлы проектов (PDF, DWG, DXF)';
COMMENT ON TABLE issues IS 'Замечания к проектной документации';
COMMENT ON TABLE norm_documents IS 'Нормативные документы (ГОСТ, СП, СНиП, ПДД)';
COMMENT ON TABLE norm_chunks IS 'Чанки нормативных документов для RAG поиска';
COMMENT ON TABLE users IS 'Пользователи системы';

COMMENT ON COLUMN issues.location_geometry IS 'Геометрия замечания в системе координат чертежа (WCS)';
COMMENT ON COLUMN issues.bounding_box IS 'Ограничивающий прямоугольник [min_x, min_y, max_x, max_y]';
COMMENT ON COLUMN issues.ai_trace IS 'Трассировка принятия решений ИИ для аудита';
