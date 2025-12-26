import fitz
import pandas as pd
from unidecode import unidecode
import re

class SplitterService:
    def __init__(self):
        pd.set_option('display.max_colwidth', None) 
        pd.set_option('display.max_rows', None)   
        pd.set_option('display.expand_frame_repr', False)

    def is_cell_empty(self, text):
        if not text or text.strip() == "":
            return True
        invisible_chars = ["\u200b", "\u200c", "\u200d"]
        for c in invisible_chars:
            text = text.replace(c, "")
        return text.strip() == ""

    def generate_fields(self, path, output_path=None, field_padding=0.0, vertical_shrink=0.9, min_vertical_gap=0.6):
        doc = fitz.open(path)
        if output_path is None:
            output_path = path.replace(".pdf", "_with_fields.pdf")

        special_pattern = re.compile(
            r"([A-Za-zÀ-ÿ0-9 :,<>'\"\n\[\]\(\)\{\}]*)((…|_|\.)[\s_.…]+(…|_|\.))([A-Za-zÀ-ÿ0-9 :,<>'\"\n\[\]\(\)\{\}]*)"
        )

        for page_number, page in enumerate(doc, start=1):
            print(f"\n- Page analysis {page_number}...")
            page_dict = page.get_text("rawdict")
            created_rects = []

            # Textual fields generation
            for block in page_dict["blocks"]:
                if block["type"] != 0:
                    continue

                for line in block["lines"]:
                    for span in line["spans"]:
                        chars = span.get("chars", [])
                        if not chars:
                            continue

                        text = "".join(ch.get("c", "") for ch in chars)
                        if not text.strip():
                            continue

                        for match in special_pattern.finditer(text):
                            start, end = match.span(2)
                            if start >= len(chars):
                                continue
                            end = min(end, len(chars))
                            seq_chars = chars[start:end]
                            if not seq_chars:
                                continue

                            seq_x0 = seq_chars[0]["bbox"][0]
                            seq_x1 = seq_chars[-1]["bbox"][2]

                            font_size = span["size"]
                            asc = span.get("ascender", 1.0)
                            desc = span.get("descender", -0.25)
                            text_height = font_size * (asc - desc)

                            baseline_y = span["origin"][1]
                            y0 = baseline_y - asc * font_size
                            y1 = y0 + text_height

                            height_reduction = (1 - vertical_shrink) * (y1 - y0)
                            y0 += height_reduction / 2 + min_vertical_gap
                            y1 -= height_reduction / 2 + min_vertical_gap

                            seq_rect = fitz.Rect(
                                seq_x0 - field_padding,
                                y0,
                                seq_x1 + field_padding,
                                y1,
                            )

                            if any(seq_rect.intersects(r) for r in created_rects):
                                continue
                            created_rects.append(seq_rect)

                            print(f"    + Field: {seq_rect} → '{match.group()}'")

                            widget = fitz.Widget()
                            widget.field_name = f"auto_field_{page_number}_{int(seq_x0)}"
                            widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                            widget.rect = seq_rect
                            widget.field_value = ""
                            widget.text_fontsize = font_size * 0.7
                            widget.text_color = (0, 0, 0)
                            widget.border_color = (0, 0, 0)
                            widget.border_width = 0.5
                            widget.fill_color = None

                            page.add_widget(widget)

            # Table fields generation
            try:
                tables = page.find_tables(horizontal_strategy="lines_strict", vertical_strategy="lines_strict")
            except Exception as e:
                print(f"find_tables error: {e}")
                continue
            if not tables or not tables.tables:
                print("Tables not found.")
                continue

            for t_index, table in enumerate(tables.tables, start=1):
                print(f"Table {t_index} with {len(table.cells)} cells.")
                created_rects = []

                for c_index, cell in enumerate(table.cells, start=1):
                    if isinstance(cell, tuple) and len(cell) >= 4:
                        x0, y0, x1, y1 = cell[:4]
                    else:
                        x0, y0, x1, y1 = cell.rect
                    rect = fitz.Rect(x0, y0, x1, y1)

                    text = page.get_textbox(rect)

                    if not self.is_cell_empty(text):
                        continue

                    if any(rect.intersects(r) for r in created_rects):
                        continue
                    created_rects.append(rect)

                    widget = fitz.Widget()
                    widget.field_name = f"table_field_{page_number}_{t_index}_{c_index}"
                    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                    widget.rect = rect
                    widget.text_fontsize = 8
                    widget.border_width = 0.5
                    page.add_widget(widget)
                    print(f"Field created: {rect}")

        doc.save(output_path, incremental=False)
        print(f"\n✅ Fields created and saved to: {output_path}")
        return output_path
        

    def extract_fields(self, path):
        doc = fitz.open(path)
        all_fields = []
        field_counter = 1

        for page in doc:
            page_bb = page.bound()
            previous_widget = None

            page_dict = page.get_text("dict")
            lines = []
            for block in page_dict["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    bbox = fitz.Rect(line["bbox"])
                    text = " ".join([span["text"] for span in line["spans"]]).strip()
                    if text:
                        lines.append((bbox, text))

            for field in page.widgets():
                field_name = field.field_name if field.field_name else f"Field_{field_counter}"
                field_rect = field.rect
                field_rect_backup = field_rect

                if previous_widget is None:
                    field_rect.x0 = page_bb.x0
                else:
                    field_rect.x0 = page_bb.x0
                    if field_rect.intersects(previous_widget):
                        field_rect.x0 = previous_widget.x1
                previous_widget = field_rect_backup

                text = page.get_textbox(field_rect_backup).strip()
                if not text:
                    lines_above = [ (bbox, t) for bbox, t in lines if bbox.y1 <= field_rect_backup.y0 ]
                    if lines_above:
                        nearest_bbox, nearest_text = max(lines_above, key=lambda x: x[0].y1)
                        if previous_widget and nearest_bbox.intersects(previous_widget):
                            text = ""
                        else:
                            text = nearest_text

                label_text = text if text else f"__________________ ({field_name})"

                all_fields.append({
                    "field_name": field_name,
                    "label_text": label_text,
                    "rect": field_rect_backup
                })

                field_counter += 1

        return all_fields


    def split(self, path):
        doc = fitz.open(path)
        
        widgets = []
        page = doc[0]
        annot = page.first_widget
        while annot:
            if annot.field_name: 
                widgets.append(annot.field_name)
            annot = annot.next
        
        if widgets:
            print("Document contains widgets, analyzing forms...")
            return path, self.extract_fields(path) 
        else:
            print("Document contains no widgets, analyzing text...")
            new_path = self.generate_fields(path)
            return new_path, self.extract_fields(new_path)
