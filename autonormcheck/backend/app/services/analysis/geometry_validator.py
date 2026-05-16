"""
Сервис геометрической валидации проектов
Использует Shapely для проверки геометрических требований
"""
import logging
from typing import Optional
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union, nearest_points

logger = logging.getLogger(__name__)


class GeometryValidator:
    """Валидатор геометрии для проверки пространственных требований норм"""
    
    def __init__(self):
        pass
    
    def validate(
        self,
        entities: list[dict],
        dimensions: list[dict],
    ) -> list[dict]:
        """
        Геометрическая валидация проекта
        
        Args:
            entities: Графические сущности
            dimensions: Размерные элементы
        
        Returns:
            Список замечаний по геометрии
        """
        issues = []
        
        # 1. Проверка пересечений конфликтующих элементов
        intersection_issues = self._check_intersections(entities)
        issues.extend(intersection_issues)
        
        # 2. Проверка минимальных расстояний
        distance_issues = self._check_minimum_distances(entities)
        issues.extend(distance_issues)
        
        # 3. Проверка углов и радиусов
        angle_issues = self._check_angles_and_radii(entities)
        issues.extend(angle_issues)
        
        # 4. Проверка площадей
        area_issues = self._check_areas(entities)
        issues.extend(area_issues)
        
        # 5. Валидация размеров
        dimension_issues = self._validate_dimensions(entities, dimensions)
        issues.extend(dimension_issues)
        
        logger.info(f"Geometry validation complete: {len(issues)} issues found")
        
        return issues
    
    def _check_intersections(self, entities: list[dict]) -> list[dict]:
        """Проверка нежелательных пересечений элементов"""
        issues = []
        
        # Группировка сущностей по типам
        roads = [e for e in entities if self._is_road_element(e)]
        sidewalks = [e for e in entities if self._is_sidewalk_element(e)]
        utilities = [e for e in entities if self._is_utility_element(e)]
        
        # Проверка пересечения дорог с коммуникациями
        for road in roads:
            road_geom = self._entity_to_shapely(road)
            if not road_geom:
                continue
            
            for utility in utilities:
                util_geom = self._entity_to_shapely(utility)
                if not util_geom:
                    continue
                
                if road_geom.intersects(util_geom):
                    issues.append({
                        "title": "Конфликт дороги и инженерных сетей",
                        "description": "Обнаружено пересечение проезжей части с инженерными коммуникациями",
                        "priority": "CRITICAL",
                        "category": "CONFLICTS",
                        "confidence_score": 0.95,
                        "regulation_reference": {
                            "document_name": "СП 34.13330.2021",
                            "section": "7.2.1",
                            "text": "Пересечение дорог с инженерными сетями должно выполняться под углом не менее 60°"
                        },
                        "location_geometry": self._shapely_to_geojson(road_geom),
                        "affected_entities": [road.get("id"), utility.get("id")],
                    })
        
        return issues
    
    def _check_minimum_distances(self, entities: list[dict]) -> list[dict]:
        """Проверка минимальных расстояний между элементами"""
        issues = []
        
        # Минимальные расстояния по нормам (в метрах)
        min_distances = {
            ("tree", "road"): 2.0,  # Деревья от края проезжей части
            ("tree", "building"): 5.0,  # Деревья от зданий
            ("pole", "road"): 0.5,  # Стойки от края проезжей части
            ("parking", "building"): 6.0,  # Парковки от зданий
        }
        
        trees = [e for e in entities if self._is_tree_element(e)]
        poles = [e for e in entities if self._is_pole_element(e)]
        roads = [e for e in entities if self._is_road_element(e)]
        buildings = [e for e in entities if self._is_building_element(e)]
        
        # Проверка деревьев от дорог
        for tree in trees:
            tree_point = self._get_entity_centroid(tree)
            if not tree_point:
                continue
            
            for road in roads:
                road_line = self._entity_to_shapely(road)
                if not road_line:
                    continue
                
                distance = tree_point.distance(road_line)
                
                if distance < min_distances[("tree", "road")]:
                    issues.append({
                        "title": "Недостаточное расстояние дерева от дороги",
                        "description": f"Дерево расположено на расстоянии {distance:.2f}м от края проезжей части (требуется минимум {min_distances[('tree', 'road')]}м)",
                        "priority": "IMPORTANT",
                        "category": "LANDSCAPING",
                        "confidence_score": 0.90,
                        "regulation_reference": {
                            "document_name": "ГОСТ Р 52289-2014",
                            "section": "6.2.5",
                            "text": "Расстояние от деревьев до края проезжей части должно быть не менее 2м"
                        },
                        "location_geometry": {"type": "Point", "coordinates": list(tree_point.coords)[0]},
                        "affected_entities": [tree.get("id"), road.get("id")],
                    })
        
        return issues
    
    def _check_angles_and_radii(self, entities: list[dict]) -> list[dict]:
        """Проверка углов пересечения и радиусов закруглений"""
        issues = []
        
        # Поиск пересечений дорог
        roads = [e for e in entities if self._is_road_element(e)]
        
        for i, road1 in enumerate(roads):
            for road2 in roads[i+1:]:
                geom1 = self._entity_to_shapely(road1)
                geom2 = self._entity_to_shapely(road2)
                
                if not geom1 or not geom2:
                    continue
                
                if geom1.intersects(geom2):
                    intersection = geom1.intersection(geom2)
                    
                    # Вычисление угла пересечения (упрощенно)
                    angle = self._calculate_intersection_angle(geom1, geom2)
                    
                    if angle and angle < 60:
                        issues.append({
                            "title": "Острый угол пересечения дорог",
                            "description": f"Угол пересечения дорог составляет {angle:.1f}° (требуется минимум 60°)",
                            "priority": "IMPORTANT",
                            "category": "ROAD_SAFETY",
                            "confidence_score": 0.85,
                            "regulation_reference": {
                                "document_name": "СП 34.13330.2021",
                                "section": "5.2.4",
                                "text": "Пересечение дорог в одном уровне должно выполняться под углом не менее 60°"
                            },
                            "location_geometry": self._shapely_to_geojson(intersection),
                            "affected_entities": [road1.get("id"), road2.get("id")],
                        })
        
        return issues
    
    def _check_areas(self, entities: list[dict]) -> list[dict]:
        """Проверка площадей элементов"""
        issues = []
        
        parking_areas = [e for e in entities if self._is_parking_area(e)]
        
        for parking in parking_areas:
            geom = self._entity_to_shapely(parking)
            if not geom or not isinstance(geom, Polygon):
                continue
            
            area = geom.area
            min_parking_area = 25.0  # м² на машиноместо (упрощенно)
            
            # Предполагаем количество мест по площади
            estimated_spaces = area / min_parking_area
            
            if area < 50:  # Минимальная парковка
                issues.append({
                    "title": "Парковка недостаточной площади",
                    "description": f"Площадь парковки {area:.1f}м² недостаточна для размещения автомобилей",
                    "priority": "RECOMMENDATION",
                    "category": "PARKING",
                    "confidence_score": 0.75,
                    "regulation_reference": {
                        "document_name": "СП 42.13330.2016",
                        "section": "11.18",
                        "text": "Площадь одного машиноместа должна составлять не менее 25м²"
                    },
                    "location_geometry": self._shapely_to_geojson(geom),
                    "affected_entities": [parking.get("id")],
                })
        
        return issues
    
    def _validate_dimensions(self, entities: list[dict], dimensions: list[dict]) -> list[dict]:
        """Валидация размерных линий"""
        issues = []
        
        # Сопоставление размеров с геометрией
        for dim in dimensions:
            measurement = dim.get("measurement")
            if not measurement:
                continue
            
            # Поиск связанного элемента
            associated_entity = self._find_dimension_target(dim, entities)
            if not associated_entity:
                continue
            
            # Проверка критических размеров
            entity_type = associated_entity.get("type", "")
            layer = associated_entity.get("layer", "").lower()
            
            # Ширина тротуара
            if "тротуар" in layer or "sidewalk" in layer:
                if measurement < 1.5:
                    issues.append({
                        "title": "Ширина тротуара меньше нормы",
                        "description": f"Замеренная ширина тротуара {measurement}м менее требуемых 1.5м",
                        "priority": "CRITICAL",
                        "category": "ACCESSIBILITY",
                        "confidence_score": 0.95,
                        "regulation_reference": {
                            "document_name": "СП 34.13330.2021",
                            "section": "5.4.2",
                            "text": "Минимальная ширина тротуаров должна составлять не менее 1.5м"
                        },
                        "location_geometry": self._entity_to_geometry(associated_entity),
                        "affected_entities": [associated_entity.get("id")],
                    })
            
            # Ширина полосы движения
            if "дорога" in layer or "road" in layer or "проезж" in layer:
                if measurement < 3.0:
                    issues.append({
                        "title": "Ширина полосы движения меньше нормы",
                        "description": f"Ширина полосы {measurement}м менее минимальных 3.0м",
                        "priority": "CRITICAL",
                        "category": "ROAD_SAFETY",
                        "confidence_score": 0.95,
                        "regulation_reference": {
                            "document_name": "СП 34.13330.2021",
                            "section": "5.3.1",
                            "text": "Ширина полосы движения должна быть не менее 3.0м"
                        },
                        "location_geometry": self._entity_to_geometry(associated_entity),
                        "affected_entities": [associated_entity.get("id")],
                    })
        
        return issues
    
    # Вспомогательные методы классификации
    def _is_road_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["дорог", "road", "проезж", "auto"])
    
    def _is_sidewalk_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["тротуар", "sidewalk", "пешеход"])
    
    def _is_utility_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["сеть", "utility", "кабель", "труб", "вод", "газ"])
    
    def _is_tree_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["дерево", "tree", "озелен", "plant"])
    
    def _is_pole_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["столб", "pole", "опор", "фонар", "свет"])
    
    def _is_building_element(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["здание", "building", "дом", "сооруж"])
    
    def _is_parking_area(self, entity: dict) -> bool:
        layer = entity.get("layer", "").lower()
        return any(kw in layer for kw in ["парков", "parking", "стоянк"])
    
    # Геометрические утилиты
    def _entity_to_shapely(self, entity: dict):
        """Преобразование сущности в объект Shapely"""
        coords = entity.get("coordinates", {})
        entity_type = entity.get("type")
        
        if entity_type == "LINE" and "start" in coords and "end" in coords:
            return LineString([coords["start"], coords["end"]])
        
        elif entity_type == "POLYLINE" and "vertices" in coords:
            vertices = coords["vertices"]
            if len(vertices) >= 2:
                return LineString(vertices)
        
        elif entity_type == "POINT" and "location" in coords:
            return Point(coords["location"])
        
        return None
    
    def _get_entity_centroid(self, entity: dict) -> Optional[Point]:
        """Получение центроида сущности"""
        geom = self._entity_to_shapely(entity)
        if geom:
            return geom.centroid
        return None
    
    def _shapely_to_geojson(self, geom):
        """Преобразование Shapely геометрии в GeoJSON"""
        from shapely.geometry import mapping
        
        if geom:
            geojson = mapping(geom)
            return {
                "type": geojson["type"],
                "coordinates": geojson["coordinates"],
            }
        return None
    
    def _entity_to_geometry(self, entity: dict):
        """Преобразование сущности в GeoJSON"""
        return self._shapely_to_geojson(self._entity_to_shapely(entity))
    
    def _calculate_intersection_angle(self, geom1, geom2) -> Optional[float]:
        """Вычисление угла пересечения двух линий (упрощенно)"""
        import math
        
        if not isinstance(geom1, LineString) or not isinstance(geom2, LineString):
            return None
        
        # Получение направлений линий
        if len(geom1.coords) < 2 or len(geom2.coords) < 2:
            return None
        
        x1, y1 = geom1.coords[0]
        x2, y2 = geom1.coords[-1]
        dx1, dy1 = x2 - x1, y2 - y1
        
        x3, y3 = geom2.coords[0]
        x4, y4 = geom2.coords[-1]
        dx2, dy2 = x4 - x3, y4 - y3
        
        # Угол между векторами
        dot_product = dx1 * dx2 + dy1 * dy2
        mag1 = math.sqrt(dx1**2 + dy1**2)
        mag2 = math.sqrt(dx2**2 + dy2**2)
        
        if mag1 == 0 or mag2 == 0:
            return None
        
        cos_angle = dot_product / (mag1 * mag2)
        angle_rad = math.acos(max(-1, min(1, cos_angle)))
        angle_deg = math.degrees(angle_rad)
        
        # Возвращаем острый угол
        return min(angle_deg, 180 - angle_deg)
    
    def _find_dimension_target(self, dimension: dict, entities: list[dict]):
        """Поиск сущности, к которой относится размер"""
        # Упрощенная реализация - поиск ближайшей сущности
        dim_coords = dimension.get("coordinates", {})
        
        if "defpoint" in dim_coords:
            target_point = Point(dim_coords["defpoint"])
            
            min_dist = float('inf')
            closest_entity = None
            
            for entity in entities:
                entity_centroid = self._get_entity_centroid(entity)
                if entity_centroid:
                    dist = target_point.distance(entity_centroid)
                    if dist < min_dist:
                        min_dist = dist
                        closest_entity = entity
            
            return closest_entity
        
        return None
