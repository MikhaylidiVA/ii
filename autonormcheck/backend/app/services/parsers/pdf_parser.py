"""
Парсер PDF файлов
Извлекает векторную графику, текст, выполняет OCR при необходимости
"""
import logging
from typing import Optional
import fitz  # PyMuPDF
import numpy as np

logger = logging.getLogger(__name__)


class PDFParser:
    """Парсер для извлечения данных из PDF"""
    
    def __init__(self, ocr_enabled: bool = True):
        self.ocr_enabled = ocr_enabled
    
    def parse(self, file_bytes: bytes) -> dict:
        """
        Парсинг PDF файла
        
        Args:
            file_bytes: Байты PDF файла
        
        Returns:
            Словарь с извлеченными данными
        """
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        extracted_data = {
            "pages_count": len(doc),
            "text_blocks": [],
            "entities": [],
            "layers": [],
            "dimensions": [],
            "metadata": {},
        }
        
        # Извлечение метаданных
        metadata = doc.metadata
        extracted_data["metadata"] = {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
        }
        
        # Обработка каждой страницы
        for page_num, page in enumerate(doc):
            logger.info(f"Processing PDF page {page_num + 1}/{len(doc)}")
            
            # Извлечение текста с позициями
            text_blocks = self._extract_text(page, page_num)
            extracted_data["text_blocks"].extend(text_blocks)
            
            # Извлечение векторной графики
            entities = self._extract_vectors(page, page_num)
            extracted_data["entities"].extend(entities)
            
            # Извлечение размеров (если есть)
            dimensions = self._extract_dimensions(page, page_num)
            extracted_data["dimensions"].extend(dimensions)
            
            # OCR для растровых элементов (если включено)
            if self.ocr_enabled:
                ocr_text = self._perform_ocr(page, page_num)
                extracted_data["text_blocks"].extend(ocr_text)
        
        # Извлечение слоев (имитация, т.к. PDF не имеет слоев как DWG)
        extracted_data["layers"] = self._infer_layers(extracted_data["entities"])
        
        doc.close()
        
        logger.info(f"PDF parsing complete: {len(extracted_data['entities'])} entities, {len(extracted_data['text_blocks'])} text blocks")
        
        return extracted_data
    
    def _extract_text(self, page: fitz.Page, page_num: int) -> list[dict]:
        """Извлечение текста с координатами"""
        text_blocks = []
        
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    bbox = span["bbox"]
                    text_blocks.append({
                        "id": f"text_p{page_num}_{len(text_blocks)}",
                        "type": "TEXT",
                        "page": page_num,
                        "text": text,
                        "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],  # x0, y0, x1, y1
                        "font": span.get("font"),
                        "size": span.get("size"),
                        "color": span.get("color"),
                    })
        
        return text_blocks
    
    def _extract_vectors(self, page: fitz.Page, page_num: int) -> list[dict]:
        """Извлечение векторной графики"""
        entities = []
        
        drawings = page.get_drawings()
        
        for i, path in enumerate(drawings):
            entity_type = self._classify_path(path)
            
            if entity_type == "LINE":
                # Линии
                for item in path.get("items", []):
                    if item[0] == "l":  # line
                        start = item[1]
                        end = item[2]
                        entities.append({
                            "id": f"line_p{page_num}_{len(entities)}",
                            "type": "LINE",
                            "page": page_num,
                            "layer": path.get("layer", "0"),
                            "coordinates": {
                                "start": [start[0], start[1]],
                                "end": [end[0], end[1]],
                            },
                            "color": path.get("color"),
                            "width": path.get("width", 1),
                        })
            
            elif entity_type == "RECT":
                # Прямоугольники
                rect = path.get("rect")
                if rect:
                    entities.append({
                        "id": f"rect_p{page_num}_{len(entities)}",
                        "type": "RECTANGLE",
                        "page": page_num,
                        "layer": path.get("layer", "0"),
                        "coordinates": {
                            "x": rect[0],
                            "y": rect[1],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1],
                        },
                        "color": path.get("color"),
                    })
            
            elif entity_type == "CIRCLE":
                # Круги (через кривые)
                entities.append({
                    "id": f"circle_p{page_num}_{len(entities)}",
                    "type": "CIRCLE",
                    "page": page_num,
                    "layer": path.get("layer", "0"),
                    "coordinates": path.get("points", []),
                    "color": path.get("color"),
                })
            
            elif entity_type == "POLYLINE":
                # Полилинии
                points = []
                for item in path.get("items", []):
                    if item[0] in ["l", "c"]:
                        points.extend([p for p in item[1:] if isinstance(p, (tuple, list))])
                
                if len(points) >= 2:
                    entities.append({
                        "id": f"polyline_p{page_num}_{len(entities)}",
                        "type": "POLYLINE",
                        "page": page_num,
                        "layer": path.get("layer", "0"),
                        "coordinates": {"vertices": [[p[0], p[1]] for p in points]},
                        "color": path.get("color"),
                        "closed": path.get("close", False),
                    })
        
        return entities
    
    def _extract_dimensions(self, page: fitz.Page, page_num: int) -> list[dict]:
        """Извлечение размерных линий (эвристически)"""
        dimensions = []
        
        # Простой эвристический поиск - линии с текстом рядом
        # В production использовать более сложный анализ
        
        return dimensions
    
    def _perform_ocr(self, page: fitz.Page, page_num: int) -> list[dict]:
        """OCR распознавание текста"""
        ocr_results = []
        
        try:
            # Рендеринг страницы в изображение
            mat = fitz.Matrix(2, 2)  # Увеличение разрешения для лучшего OCR
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            
            # PaddleOCR
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='ru', show_log=False)
            results = ocr.ocr(img, cls=True)
            
            if results and results[0]:
                for line in results[0]:
                    bbox = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    
                    # Преобразование координат обратно в PDF
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height
                    
                    ocr_results.append({
                        "id": f"ocr_p{page_num}_{len(ocr_results)}",
                        "type": "TEXT_OCR",
                        "page": page_num,
                        "text": text,
                        "bbox": [
                            bbox[0][0] * scale_x,
                            bbox[0][1] * scale_y,
                            bbox[2][0] * scale_x,
                            bbox[2][1] * scale_y,
                        ],
                        "confidence": confidence,
                    })
        
        except Exception as e:
            logger.warning(f"OCR failed on page {page_num}: {e}")
        
        return ocr_results
    
    def _classify_path(self, path: dict) -> str:
        """Классификация типа графического примитива"""
        items = path.get("items", [])
        rect = path.get("rect")
        
        if rect and len(rect) == 4:
            return "RECT"
        
        if len(items) >= 4 and path.get("close"):
            # Проверка на круг/эллипс
            return "CIRCLE"
        
        if len(items) > 2:
            return "POLYLINE"
        
        if len(items) == 1 and items[0][0] == "l":
            return "LINE"
        
        return "UNKNOWN"
    
    def _infer_layers(self, entities: list[dict]) -> list[str]:
        """Инференс слоев из сущностей"""
        layers = set()
        for entity in entities:
            layer = entity.get("layer", "0")
            if layer:
                layers.add(str(layer))
        return sorted(list(layers))
