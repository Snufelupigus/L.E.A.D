import json
import os
import datetime

class Backend:
    def __init__(self, data_file="component_catalogue.json", changelog_file="changelog.txt"):
        script_dir = os.path.dirname(os.path.abspath(__file__))  # Get directory of backend.py
        self.data_file = os.path.join(script_dir, "component_catalogue.json")  # Set full path
        self.changelog_file = os.path.join(script_dir, changelog_file)
        self.components = []
        self.load_components()
        self.max_leds = 300

    def load_components(self):
        try:
            with open(self.data_file, "r") as file:
                self.components = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.components = []

    def save_components(self):
        with open(self.data_file, "w") as file:
            json.dump(self.components, file, indent=4)
            print(f"Data saved to: {os.path.abspath(self.data_file)}")

        self.log_change("Saved components file.")

    def log_change(self, message):
        # Appends a timestamped log message to the changelog file.
        timestamp = datetime.datetime.now().isoformat()
        with open(self.changelog_file, "a") as log_file:
            log_file.write(f"{timestamp} - {message}\n")

    def index_to_location(self, index):
        """
        Converts a 0-based index into a location code.
        For example, index 0 -> "1A", index 1 -> "1B", ... index 26 -> "2A", etc.
        """
        row = index // 26 + 1
        col = index % 26
        return f"{row}{chr(col + ord('A'))}"

    def get_assigned_locations(self):
        """
        Returns a set of all location codes already assigned to components.
        """
        assigned = set()
        for comp in self.components:
            loc = comp["part_info"].get("location", "").strip().upper()
            if loc:
                assigned.add(loc)
        return assigned

    def assign_location(self):
        """
        Finds the earliest free location code (based on LED index order) that is not
        currently assigned. Returns the location code as a string (e.g., "1A").
        """
        assigned = self.get_assigned_locations()
        for i in range(self.max_leds):
            candidate = self.index_to_location(i)
            if candidate not in assigned:
                return candidate
        return None  # No free location available

    def add_component(self, component):
        """
        Adds a new component. If the location field is empty, automatically
        assign the next free location.
        Also, if a component with the same part number exists, you could choose
        to update it instead.
        """
        new_part_number = component["part_info"]["part_number"].strip().lower()
        new_count = int(component["part_info"].get("count", 0))

        # Check the location. If it's empty or "N/A", assign a new location.
        location = component["part_info"].get("location", "").strip()
        if not location or location.upper() == "N/A":
            auto_loc = self.assign_location()
            if auto_loc is not None:
                component["part_info"]["location"] = auto_loc
            else:
                component["part_info"]["location"] = "N/A"  # Or raise an error

        # (Optional) Check for duplicates and update count if needed.
        duplicate_index = None
        for i, comp in enumerate(self.components):
            existing_part = comp["part_info"]["part_number"].strip().lower()
            if existing_part == new_part_number:
                duplicate_index = i
                break

        if duplicate_index is not None:
            existing_component = self.components[duplicate_index]
            try:
                existing_count = int(existing_component["part_info"].get("count", 0))
            except ValueError:
                existing_count = 0
            updated_count = existing_count + new_count
            existing_component["part_info"]["count"] = updated_count
            self.components[duplicate_index] = existing_component
        else:
            # Insert new component at the beginning of the list
            self.components.insert(0, component)

        self.save_components()

    def get_all_components(self):
        return self.components

    def search_components(self, query):
        query = query.lower()
        return [
            comp for comp in self.components
            if any(query in str(value).lower() for value in comp["part_info"].values())
        ]

    def edit_component(self, index, updated_component):
        if 0 <= index < len(self.components):
            old_part = self.components[index]["part_info"].get("part_number", "Unknown")
            self.components[index] = updated_component
            self.save_components()
            self.log_change(f"Edited component at index {index} (Part Number: {old_part}).")

    def delete_component(self, index):
        if 0 <= index < len(self.components):
            removed = self.components.pop(index)
            self.save_components()
            removed_part = removed["part_info"].get("part_number", "Unknown")
            self.log_change(f"Deleted component at index {index} (Part Number: {removed_part}).")

    def get_statistics(self):
        total_parts = len(self.components)
        types = set(comp["part_info"]["type"] for comp in self.components)
        return {"total_parts": total_parts, "types": list(types)}
    
    def barcode_decoder(self, barcode):
        # Validate and remove header
        if not barcode.startswith("[)>"):
            raise ValueError("Invalid barcode format")
        
        remaining = barcode[6:]

        part_number = remaining.split("1P")
        count = part_number[1].split("4L")
        part_number = part_number[0]
        count = count[1].split("Q")
        count = count[1].split("11Z")
        count = count[0]

        print(part_number)
        print(count)

        parsed_data = {
            "part_number": part_number,
            "count": count,
        }
        return parsed_data

#Begining([)>06P) Digikey #(455-1135-1-ND) 1P Manufacturer # (SXH-001T-P0.6) 30P Digikey # (455-1135-1-ND) K1K 90743192 10K 1097944959D2024.091T40380411K14LCN Quantity(Q20) 11ZPICK12Z52737013Z99999920Z0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
#[)>06P455-1135-1-ND1PSXH-001T-P0.630P455-1135-1-NDK1K9074319210K1097944959D2024.091T40380411K14LCNQ2011ZPICK12Z52737013Z99999920Z0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

    def check_duplicate(self, component):
        new_part_number = component["part_number"].strip().lower()
        new_count = int(component.get("count", 0))
        duplicate_index = None

        for i, comp in enumerate(self.components):
            existing_part_number = comp["part_info"]["part_number"].strip().lower()
            if existing_part_number == new_part_number:
                duplicate_index = i
                break

        if duplicate_index is not None:
            # Component exists; update its count.
            existing_component = self.components[duplicate_index]
            try:
                existing_count = int(existing_component["part_info"].get("count", 0))
            except ValueError:
                existing_count = 0

            updated_count = existing_count + new_count
            existing_component["part_info"]["count"] = updated_count
            self.components[duplicate_index] = existing_component
            print(f"Updated component {new_part_number} count to {updated_count}")
            self.log_change(f"Updated component '{new_part_number}': count increased from {existing_count} to {updated_count}.")
            self.save_components()
            return False
        else:
            # No duplicate found; add the new component.
            self.log_change(f"Added new component '{new_part_number}' with count {new_count}.")
            return True

    def get_low_stock_components(self):
        """
        Returns a list of components for which the current count is less than
        the low stock threshold (which is stored in the metadata).
        """
        low_stock_components = []
        for comp in self.components:
            try:
                count = int(comp["part_info"].get("count", 0))
            except (ValueError, TypeError):
                count = 0
            low_stock_value = comp["metadata"].get("low_stock")
            try:
                low_stock_value_int = int(low_stock_value)
            except (ValueError, TypeError):
                continue  # Skip components with no valid low_stock value
            
            if count < low_stock_value_int:
                low_stock_components.append(comp)
        return low_stock_components
    
    def process_bom(self, bom_list):
        """
        For each BOM row (a dictionary with at least:
            "digikey": Digi-Key part number,
            "quantity": quantity used as string,
            "found": True/False),
        this method subtracts the used quantity from the count of found components.
        Returns a list of result dictionaries with keys: "part", "remaining", "status".
        """
        results = []
        for row in bom_list:
            digikey = row.get("digikey", "").strip()
            try:
                quantity_used = int(row.get("quantity", 0))
            except ValueError:
                quantity_used = 0

            if row.get("found"):
                # Find the component in the catalogue
                for comp in self.components:
                    comp_digikey = comp["part_info"].get("part_number", "").strip()
                    if comp_digikey.lower() == digikey.lower():
                        try:
                            current_count = int(comp["part_info"].get("count", 0))
                        except ValueError:
                            current_count = 0
                        new_count = current_count - quantity_used
                        comp["part_info"]["count"] = new_count
                        results.append({
                            "part": digikey,
                            "remaining": new_count,
                            "status": "Updated"
                        })
                        break
            else:
                results.append({
                    "part": digikey,
                    "remaining": "N/A",
                    "status": "Not found in catalogue"
                })
        self.save_components()  # Save updated inventory.
        return results