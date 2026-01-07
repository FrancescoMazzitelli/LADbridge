import fitz
import re
import shutil
import tempfile

class ComposerService:
    def extract_filled_field(self, fields):
        """
        Extract all values enclosed in <FIELD>...</FIELD> tags
        and return them in a list in the order they appear.
        """
        pattern = re.compile(r"<\/think><FIELD>\s*([^<]*)\s*<\/FIELD>", re.IGNORECASE)
        print(f"Analyzing chunk for fields:\n{fields}\n")
        
        if "<FIELD>" not in fields:
            print("⚠️ No <FIELD> tags found in the response, inserting placeholder '--'.")
            return ["--"]
        
        for match in pattern.finditer(fields):
            if match is None:
                continue
            
            value = match.group(1)
            
            if value is not None and value.strip() != "":
                print(f"📋 Extracted value: '{value.strip()}'")
                return [value.strip()]
        
        print("⚠️ No valid <FIELD> value found, inserting placeholder '--'.")
        return ["--"]

    def fill_pdf_form(self, template_path, output_path, ordered_values):
        """
        Fill PDF form fields in the order they are found in the file,
        """
        doc = fitz.open(template_path)
        i = 0
        
        for page_num, page in enumerate(doc, start=1):
            widget = page.first_widget
            
            while widget:
                current_value = widget.field_value if hasattr(widget, "field_value") else None
                field_name = widget.field_name or f"Field_{i+1}"
                
                if current_value and str(current_value).strip():
                    print(f"🟡 Field '{field_name}' already compiled with '{current_value}' → skip")
                else:
                    if i < len(ordered_values):
                        new_value = str(ordered_values[i])
                        widget.field_value = new_value
                        widget.update()
                        print(f"🟢 Field '{field_name}' (#{i+1}) ← '{new_value}'")
                        i += 1
                    else:
                        print(f"⚠️ No value provided for '{field_name}', leaving it empty.")
                
                widget = widget.next
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            temp_path = tmp.name
        
        doc.save(temp_path)
        doc.close()
        shutil.move(temp_path, output_path)
        print(f"✅ Compiled pdf saved as: {output_path}")