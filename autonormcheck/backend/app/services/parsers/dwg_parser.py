"""
Парсер DWG/DXF файлов
Извлекает векторную графику, слои, текст, размеры
"""
import logging
import tempfile
import os
from typing import Optional
import ezdxf
from ezdxf import Recover

logger = logging.getLogger(__name__)


class DWGParser:
    """Парсер для извлечения данных из DWG/DXF файлов"""
    
    def __init__(self):
        pass
    
    def parse(self, file_bytes: bytes) -> dict:
        """
        Парсинг DWG/DXF файла
        
        Args:
            file_bytes: Байты DWG/DXF файла
        
        Returns:
            Словарь с извлеченными данными
        """
        # Проверка формата и конвертация если нужно
        is_dwg = file_bytes[:4] == b'\x41\x43\x31\x00' or file_bytes[:6] in [b'AC1015', b'AC1018', b'AC1021', b'AC1024', b'AC1027', b'AC1032']
        
        if is_dwg:
            # Конвертация DWG -> DXF через временный файл
            # В production использовать ODA File Converter
            logger.warning("DWG format detected. ODA converter not available, attempting direct parse.")
            # Попытка прочитать как DXF (может не сработать для бинарного DWG)
            return self._parse_fallback(file_bytes)
        
        return self._parse_dxf(file_bytes)
    
    def _parse_dxf(self, file_bytes: bytes) -> dict:
        """Парсинг DXF файла"""
        extracted_data = {
            "text_blocks": [],
            "entities": [],
            "layers": [],
            "dimensions": [],
            "blocks": [],
            "metadata": {},
        }
        
        try:
            # Чтение DXF из байтов
            from io import BytesIO
            doc = ezdxf.readfile(BytesIO(file_bytes))
        except Exception as e:
            logger.error(f"Failed to read DXF: {e}")
            raise ValueError(f"Invalid DXF file: {e}")
        
        # Извлечение метаданных
        header = doc.header
        extracted_data["metadata"] = {
            "version": doc.dxfversion,
            "units": str(header.get('$INSUNITS', 'unknown')),
            "extmin": list(header.get('$EXTMIN', (0, 0, 0))),
            "extmax": list(header.get('$EXTMAX', (0, 0, 0))),
        }
        
        # Извлечение слоев
        layers = []
        for layer in doc.layers:
            layers.append({
                "name": layer.dxf.name,
                "color": layer.dxf.color if hasattr(layer.dxf, 'color') else None,
                "linetype": layer.dxf.linetype if hasattr(layer.dxf, 'linetype') else None,
                "frozen": layer.is_frozen(),
                "locked": layer.is_locked(),
            })
        extracted_data["layers"] = layers
        
        # Обработка modelspace
        msp = doc.modelspace()
        extracted_data["entities"] = self._extract_entities(msp)
        
        # Обработка блоков
        for block in doc.blocks:
            if block.name.startswith('*'):  # Системные блоки пропускаем
                continue
            
            block_entities = self._extract_entities(block)
            extracted_data["blocks"].append({
                "name": block.name,
                "base_point": list(block.base_point) if hasattr(block, 'base_point') else [0, 0, 0],
                "entities": block_entities,
            })
        
        # Извлечение текстовых элементов
        extracted_data["text_blocks"] = self._extract_texts(msp)
        
        # Извлечение размеров
        extracted_data["dimensions"] = self._extract_dimensions(msp)
        
        doc.close()
        
        logger.info(f"DXF parsing complete: {len(extracted_data['entities'])} entities, {len(extracted_data['layers'])} layers")
        
        return extracted_data
    
    def _parse_fallback(self, file_bytes: bytes) -> dict:
        """Fallback парсинг для DWG (ограниченная поддержка)"""
        # В production здесь будет вызов ODA File Converter
        # odaconvert input.dwg output.dxf
        
        logger.warning("Using fallback parser for DWG. Consider installing ODA File Converter.")
        
        # Попытка прочитать как DXF (работает только если файл на самом деле DXF)
        try:
            return self._parse_dxf(file_bytes)
        except:
            return {
                "text_blocks": [],
                "entities": [],
                "layers": [],
                "dimensions": [],
                "blocks": [],
                "metadata": {"error": "DWG format requires ODA File Converter"},
            }
    
    def _extract_entities(self, layout) -> list[dict]:
        """Извлечение графических сущностей"""
        entities = []
        
        for entity in layout:
            try:
                entity_data = self._parse_entity(entity)
                if entity_data:
                    entities.append(entity_data)
            except Exception as e:
                logger.warning(f"Failed to parse entity {entity.dxftype()}: {e}")
                continue
        
        return entities
    
    def _parse_entity(self, entity) -> Optional[dict]:
        """Парсинг отдельной сущности"""
        entity_type = entity.dxftype()
        
        base_data = {
            "id": f"{entity_type}_{entity.handle}" if hasattr(entity, 'handle') else f"{entity_type}_{id(entity)}",
            "type": entity_type,
            "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else "0",
            "handle": entity.handle if hasattr(entity, 'handle') else None,
        }
        
        if entity_type == 'LINE':
            base_data["coordinates"] = {
                "start": list(entity.dxf.start),
                "end": list(entity.dxf.end),
            }
            base_data["length"] = self._calculate_length(entity.dxf.start, entity.dxf.end)
        
        elif entity_type == 'CIRCLE':
            base_data["coordinates"] = {
                "center": list(entity.dxf.center),
                "radius": entity.dxf.radius,
            }
        
        elif entity_type == 'ARC':
            base_data["coordinates"] = {
                "center": list(entity.dxf.center),
                "radius": entity.dxf.radius,
                "start_angle": entity.dxf.start_angle,
                "end_angle": entity.dxf.end_angle,
            }
        
        elif entity_type == 'POLYLINE' or entity_type == 'LWPOLYLINE':
            vertices = [list(v.dxf.location) if hasattr(v, 'dxf') and hasattr(v.dxf, 'location') else list(v) 
                       for v in entity.get_points()]
            base_data["coordinates"] = {
                "vertices": [[v[0], v[1]] for v in vertices],
                "closed": entity.is_closed,
            }
        
        elif entity_type == 'POINT':
            base_data["coordinates"] = {
                "location": list(entity.dxf.location),
            }
        
        elif entity_type == 'INSERT':
            base_data["coordinates"] = {
                "insert": list(entity.dxf.insert),
            }
            base_data["block_name"] = entity.dxf.name
            base_data["x_scale"] = entity.dxf.xscale
            base_data["y_scale"] = entity.dxf.yscale
        
        elif entity_type == 'MTEXT' or entity_type == 'TEXT':
            base_data["text"] = entity.plain_text() if hasattr(entity, 'plain_text') else str(entity.dxf.text)
            base_data["coordinates"] = {
                "insert": list(entity.dxf.insert) if hasattr(entity.dxf, 'insert') else [0, 0, 0],
            }
            base_data["height"] = entity.dxf.height if hasattr(entity.dxf, 'height') else None
        
        elif entity_type == 'DIMENSION':
            base_data["dimtype"] = entity.dxf.dimtype
            base_data["defpoint"] = list(entity.dxf.defpoint) if hasattr(entity.dxf, 'defpoint') else []
        
        elif entity_type == 'SPLINE':
            control_points = [list(p) for p in entity.control_points]
            base_data["coordinates"] = {
                "control_points": [[p[0], p[1]] for p in control_points],
                "degree": entity.dxf.degree,
            }
        
        elif entity_type == 'HATCH':
            base_data["pattern"] = entity.dxf.pattern_name
            base_data["solid"] = entity.dxf.solid
        
        # Добавление цвета и других атрибутов
        if hasattr(entity.dxf, 'color'):
            base_data["color"] = entity.dxf.color
        
        if hasattr(entity.dxf, 'linetype'):
            base_data["linetype"] = entity.dxf.linetype
        
        if hasattr(entity.dxf, 'lineweight'):
            base_data["lineweight"] = entity.dxf.lineweight
        
        return base_data
    
    def _extract_texts(self, layout) -> list[dict]:
        """Извлечение текстовых элементов"""
        texts = []
        
        for entity in layout:
            if entity.dxftype() in ['TEXT', 'MTEXT']:
                text_data = self._parse_entity(entity)
                if text_data:
                    texts.append(text_data)
        
        return texts
    
    def _extract_dimensions(self, layout) -> list[dict]:
        """Извлечение размерных элементов"""
        dimensions = []
        
        for entity in layout:
            if entity.dxftype() == 'DIMENSION':
                dim_data = self._parse_entity(entity)
                if dim_data:
                    # Попытка извлечь значение размера
                    try:
                        dim_data["measurement"] = entity.measurement()
                    except:
                        dim_data["measurement"] = None
                    dimensions.append(dim_data)
        
        return dimensions
    
    def _calculate_length(self, start, end) -> float:
        """Вычисление длины линии"""
        import math
        return math.sqrt(
            (end[0] - start[0])**2 + 
            (end[1] - start[1])**2 + 
            (end[2] - start[2])**2 if len(start) > 2 else 0
        )
