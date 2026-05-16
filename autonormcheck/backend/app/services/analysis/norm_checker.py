"""
Сервис проверки соответствия нормам с использованием RAG и LLM
"""
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NormChecker:
    """Сервис проверки проектной документации на соответствие нормам"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.embedding_service = None
        self.rag_search = None
    
    def _get_embedding_service(self):
        if self.embedding_service is None:
            from app.services.embeddings.embedding_service import EmbeddingService
            self.embedding_service = EmbeddingService()
        return self.embedding_service
    
    def _get_rag_search(self):
        if self.rag_search is None:
            from app.core.qdrant_client import norms_search
            self.rag_search = norms_search
        return self.rag_search
    
    def check_compliance(
        self,
        entities: list[dict],
        text_blocks: list[dict],
        layers: list[str],
    ) -> list[dict]:
        """
        Проверка соответствия нормам
        
        Args:
            entities: Графические сущности из файла
            text_blocks: Текстовые блоки
            layers: Слои чертежа
        
        Returns:
            Список замечаний
        """
        issues = []
        
        # 1. Анализ текстовых выносок и поиск релевантных норм
        text_issues = self._analyze_text_annotations(text_blocks)
        issues.extend(text_issues)
        
        # 2. Геометрический анализ сущностей
        geometry_issues = self._analyze_geometry(entities)
        issues.extend(geometry_issues)
        
        # 3. Анализ слоев
        layer_issues = self._analyze_layers(layers, entities)
        issues.extend(layer_issues)
        
        # 4. Комплексный анализ через LLM
        llm_issues = self._llm_complex_analysis(entities, text_blocks)
        issues.extend(llm_issues)
        
        logger.info(f"Norm check complete: {len(issues)} issues found")
        
        return issues
    
    def _analyze_text_annotations(self, text_blocks: list[dict]) -> list[dict]:
        """Анализ текстовых аннотаций и поиск нарушений по ключевым словам"""
        issues = []
        
        # Ключевые слова для поиска потенциальных проблем
        critical_keywords = {
            "ширина": self._check_width_requirements,
            "высота": self._check_height_requirements,
            "расстояние": self._check_distance_requirements,
            "уклон": self._check_slope_requirements,
            "радиус": self._check_radius_requirements,
        }
        
        for text_block in text_blocks:
            text = text_block.get("text", "").lower()
            
            for keyword, check_func in critical_keywords.items():
                if keyword in text:
                    # Извлечение числового значения
                    value = self._extract_numeric_value(text)
                    if value:
                        check_result = check_func(value, keyword, text_block)
                        if check_result:
                            issues.append(check_result)
        
        return issues
    
    def _analyze_geometry(self, entities: list[dict]) -> list[dict]:
        """Геометрический анализ сущностей"""
        issues = []
        
        from shapely.geometry import LineString, Point, Polygon
        from shapely.ops import unary_union
        
        for entity in entities:
            entity_type = entity.get("type")
            
            # Проверка дорог/тротуаров
            if entity_type in ["LINE", "POLYLINE"]:
                coords = entity.get("coordinates", {})
                
                if "vertices" in coords:
                    vertices = coords["vertices"]
                    if len(vertices) >= 2:
                        # Вычисление длины
                        length = self._calculate_polyline_length(vertices)
                        
                        # Поиск связанных размерных линий
                        dimension = self._find_associated_dimension(entity, entities)
                        if dimension and dimension.get("measurement"):
                            measured_value = dimension["measurement"]
                            
                            # Проверка на соответствие типичным нормам
                            if entity.get("layer", "").lower() in ["тротуар", "sidewalk", "пешеход"]:
                                if measured_value < 1.5:
                                    issues.append(self._create_issue(
                                        title="Недостаточная ширина тротуара",
                                        description=f"Ширина тротуара {measured_value}м менее минимально требуемых 1.5м",
                                        priority="CRITICAL",
                                        category="ACCESSIBILITY",
                                        regulation={
                                            "document_name": "СП 34.13330.2021",
                                            "section": "5.4.2",
                                            "text": "Минимальная ширина тротуаров должна составлять не менее 1.5м"
                                        },
                                        location=self._entity_to_geometry(entity),
                                        confidence=0.85,
                                    ))
                
                elif "start" in coords and "end" in coords:
                    # Простая линия
                    length = self._calculate_distance(coords["start"], coords["end"])
        
        return issues
    
    def _analyze_layers(self, layers: list[str], entities: list[dict]) -> list[dict]:
        """Анализ слоев на наличие обязательных элементов"""
        issues = []
        
        # Обязательные слои для дорожных проектов
        required_layers_patterns = [
            ("дорога", "Проезжая часть"),
            ("тротуар", "Тротуар"),
            ("бордюр", "Бортовое ограждение"),
            ("разметк", "Дорожная разметка"),
            ("знак", "Дорожные знаки"),
        ]
        
        layers_lower = [l.lower() for l in layers]
        
        for pattern, name in required_layers_patterns:
            found = any(pattern in layer for layer in layers_lower)
            if not found:
                # Проверка есть ли вообще сущности этого типа
                has_entities = self._has_entity_type_by_name(entities, pattern)
                
                if not has_entities:
                    issues.append(self._create_issue(
                        title=f"Отсутствует слой '{name}'",
                        description=f"На чертеже не обнаружен слой или элементы, относящиеся к '{name}'",
                        priority="IMPORTANT",
                        category="MISSING_ELEMENTS",
                        regulation={
                            "document_name": "ГОСТ Р 52289-2014",
                            "section": "4.2",
                            "text": "Проект должен содержать все необходимые элементы организации дорожного движения"
                        },
                        location=None,
                        confidence=0.70,
                    ))
        
        return issues
    
    def _llm_complex_analysis(self, entities: list[dict], text_blocks: list[dict]) -> list[dict]:
        """Комплексный анализ с использованием LLM"""
        issues = []
        
        try:
            # Подготовка контекста для LLM
            context = self._prepare_llm_context(entities, text_blocks)
            
            # RAG поиск релевантных норм
            relevant_norms = self._search_relevant_norms(context)
            
            # Формирование промпта
            prompt = self._build_analysis_prompt(context, relevant_norms)
            
            # Вызов LLM (в production использовать локальную модель)
            llm_response = self._call_llm(prompt)
            
            # Парсинг ответа LLM
            if llm_response:
                llm_issues = self._parse_llm_response(llm_response, entities, text_blocks)
                issues.extend(llm_issues)
        
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            # Fallback на rule-based проверку
            issues.extend(self._rule_based_fallback(entities, text_blocks))
        
        return issues
    
    def _search_relevant_norms(self, context: str) -> list[dict]:
        """RAG поиск релевантных нормативных документов"""
        embedding_service = self._get_embedding_service()
        rag_search = self._get_rag_search()
        
        # Генерация эмбеддинга запроса
        query_vector = embedding_service.embed_text(context)
        
        # Поиск в Qdrant
        results = rag_search.search_similar(
            query_vector=query_vector,
            limit=10,
            status="active",
        )
        
        return results
    
    def _create_issue(
        self,
        title: str,
        description: str,
        priority: str,
        category: str,
        regulation: dict,
        location: Optional[dict],
        confidence: float,
        suggestion: Optional[str] = None,
    ) -> dict:
        """Создание структурированного замечания"""
        return {
            "title": title,
            "description": description,
            "suggestion": suggestion or self._generate_suggestion(category, description),
            "priority": priority,
            "category": category,
            "confidence_score": confidence,
            "regulation_reference": {
                "document_id": regulation.get("document_id", ""),
                "document_name": regulation.get("document_name", ""),
                "document_type": self._get_document_type(regulation.get("document_name", "")),
                "section": regulation.get("section", ""),
                "full_text": regulation.get("text", ""),
                "url": "",
            },
            "location_geometry": location,
            "bounding_box": self._geometry_to_bbox(location) if location else None,
            "affected_entities": [],
            "ai_trace": {
                "timestamp": datetime.utcnow().isoformat(),
                "method": "hybrid_rag_llm",
            },
        }
    
    def _entity_to_geometry(self, entity: dict) -> Optional[dict]:
        """Преобразование сущности в GeoJSON геометрию"""
        coords = entity.get("coordinates", {})
        entity_type = entity.get("type")
        
        if entity_type == "LINE" and "start" in coords and "end" in coords:
            return {
                "type": "LineString",
                "coordinates": [coords["start"], coords["end"]],
            }
        
        elif entity_type == "POLYLINE" and "vertices" in coords:
            return {
                "type": "LineString",
                "coordinates": coords["vertices"],
            }
        
        elif entity_type == "POINT" and "location" in coords:
            return {
                "type": "Point",
                "coordinates": coords["location"],
            }
        
        return None
    
    def _geometry_to_bbox(self, geometry: Optional[dict]) -> Optional[list]:
        """Преобразование геометрии в bounding box"""
        if not geometry:
            return None
        
        coords = geometry.get("coordinates", [])
        
        if geometry["type"] == "Point":
            x, y = coords[0], coords[1]
            return [x - 0.5, y - 0.5, x + 0.5, y + 0.5]
        
        elif geometry["type"] == "LineString":
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            return [min(xs), min(ys), max(xs), max(ys)]
        
        return None
    
    # Вспомогательные методы
    def _extract_numeric_value(self, text: str) -> Optional[float]:
        import re
        numbers = re.findall(r'[\d,]+\.?\d*', text.replace(',', '.'))
        if numbers:
            try:
                return float(numbers[0].replace(',', '.'))
            except:
                pass
        return None
    
    def _calculate_distance(self, point1: list, point2: list) -> float:
        import math
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(point1[:2], point2[:2])))
    
    def _calculate_polyline_length(self, vertices: list[list]) -> float:
        total = 0
        for i in range(len(vertices) - 1):
            total += self._calculate_distance(vertices[i], vertices[i + 1])
        return total
    
    def _get_document_type(self, doc_name: str) -> str:
        if "ГОСТ" in doc_name.upper():
            return "ГОСТ"
        elif "СП" in doc_name.upper():
            return "СП"
        elif "СНиП" in doc_name.upper():
            return "СНиП"
        elif "ПДД" in doc_name.upper():
            return "ПДД"
        return "OTHER"
    
    def _generate_suggestion(self, category: str, description: str) -> str:
        suggestions = {
            "ACCESSIBILITY": "Увеличить размер до соответствия минимальным требованиям нормы.",
            "ROAD_SAFETY": "Пересмотреть проект с учетом требований безопасности дорожного движения.",
            "MISSING_ELEMENTS": "Добавить недостающие элементы в проектную документацию.",
        }
        return suggestions.get(category, "Требуется дополнительная экспертиза проекта.")
    
    # Заглушки для методов, требующих дополнительной реализации
    def _check_width_requirements(self, value, keyword, text_block):
        return None
    
    def _check_height_requirements(self, value, keyword, text_block):
        return None
    
    def _check_distance_requirements(self, value, keyword, text_block):
        return None
    
    def _check_slope_requirements(self, value, keyword, text_block):
        return None
    
    def _check_radius_requirements(self, value, keyword, text_block):
        return None
    
    def _find_associated_dimension(self, entity, entities):
        return None
    
    def _has_entity_type_by_name(self, entities, pattern):
        return False
    
    def _prepare_llm_context(self, entities, text_blocks):
        return " ".join([t.get("text", "") for t in text_blocks[:20]])
    
    def _build_analysis_prompt(self, context, norms):
        return f"Analyze: {context}"
    
    def _call_llm(self, prompt):
        return None
    
    def _parse_llm_response(self, response, entities, text_blocks):
        return []
    
    def _rule_based_fallback(self, entities, text_blocks):
        return []
