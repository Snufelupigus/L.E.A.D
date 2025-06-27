import json
from tkinter import messagebox
import os
import time
import csv
import shutil
import difflib
import datetime
import threading
from collections import OrderedDict
import datetime

class Backend:
    def __init__(self, ledControl, data_file=None, changelog_file=None):
        self.ledControl = ledControl

        script_dir = os.path.dirname(os.path.abspath(__file__))  # Get directory of backend.py

        database_folder = os.path.join(script_dir, "Databases")
        config_path = os.path.join(database_folder, "config.json")

        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                print("Error: Could not parse config.json. Using default file names.")
        else:
            print("Config file not found. Using default file names.")

        if data_file is None:
            data_file_rel = config.get("FILES", {}).get("COMPONENT_CATALOGUE", "Databases/component_catalogue.json")
            data_file = os.path.join(script_dir, data_file_rel) if not os.path.isabs(data_file_rel) else data_file_rel
        if changelog_file is None:
            changelog_file_rel = config.get("FILES", {}).get("CHANGELOG", "Databases/changelog.txt")
            changelog_file = os.path.join(script_dir, changelog_file_rel) if not os.path.isabs(changelog_file_rel) else changelog_file_rel

        self.data_file = data_file
        self.changelog_file = changelog_file

        self.components = []
        self.load_components()
        self.max_leds = 300
        self.undo_stack = []

        print("Using catalogue file:", self.data_file)

        self.last_activity = datetime.datetime.now()

        self.schedule_backup(interval_seconds=600)

    def load_components(self):
        try:
            with open(self.data_file, "r") as file:
                self.components = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.components = []

    def save_components(self):
        self.last_activity = datetime.datetime.now()
        with open(self.data_file, "w") as file:
            json.dump(self.components, file, indent=4)
            print(f"Data saved to: {os.path.abspath(self.data_file)}")

        self.log_change("Saved components file.")

    def log_change(self, message):
        # Appends a timestamped log message to the changelog file.
        timestamp = datetime.datetime.now().isoformat()
        catalogue_file = os.path.basename(self.data_file)
        with open(self.changelog_file, "a") as log_file:
            log_file.write(f"{timestamp} - {message} - Saved to: {catalogue_file}.\n")

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

        else:
            #Check for duplicate locations
            location = location.upper()
            assigned = self.get_assigned_locations()
            if location in assigned and "bin" not in location.lower():
                # Location is already taken.
                messagebox.showerror("Location Error", f"Location {location} is already assigned to another component.")
                raise Exception(f"Location {location} is already assigned to another component.")
        
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
            or any(query in str(value).lower() for value in comp["metadata"].values())
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
            self.undo_stack.append((removed, index))
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
            messagebox.showwarning("Barcode Format", f"Invalid barcode format, please try again")
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

    # TODO:tariq maybe seperate the check from the actual updating the part
    def check_duplicate(self, component):
        """
        Checks if the component is a duplicate of an existing one using fuzzy matching.
        If a near duplicate is found, it pops up a message box asking the user if they meant the similar part.
        If the user confirms, it updates the count of the existing component, logs the change, and returns False.
        If no duplicate is found, it returns True.
        
        Parameters:
            component (dict): A dictionary containing at least "part_info" with keys "part_number" and "count".
        
        Returns:
            bool: True if the component is new (i.e. not a duplicate), False if it is a duplicate.
        """
        # Get the new part number (lowercased) and count.
        new_part_number = component["part_number"].strip().lower()
        try:
            new_count = int(component.get("count", 0))
        except ValueError:
            new_count = 0

        # Get all existing part numbers from the catalogue.
        existing_components = self.get_all_components()
        existing_parts = [
            comp.get("part_info", {}).get("part_number", "").strip().lower() 
            for comp in existing_components 
            if comp.get("part_info", {}).get("part_number")
        ]

        # Exact duplicate check.
        if new_part_number in existing_parts:
            for comp in existing_components:
                if comp.get("part_info", {}).get("part_number", "").strip().lower() == new_part_number:
                    try:
                        existing_count = int(comp["part_info"].get("count", 0))
                    except ValueError:
                        existing_count = 0
                    updated_count = existing_count + new_count
                    comp["part_info"]["count"] = updated_count

                    messagebox.showinfo("Found Duplicate", f"Component {comp['part_info']['part_number']} already exists.\nAdded {comp['part_info']['count']} units.")
                    loc = comp["part_info"]["location"]
                    self.ledControl.set_led_on(loc, 0, 255, 0)
                    messagebox.showinfo("Fill Vial", f"Fill vial at {loc}.")
                    self.ledControl.turn_off_led(loc)

                    # Log the change.
                    self.log_change(
                        f"Updated component '{new_part_number}' count from {existing_count} to {updated_count} (exact duplicate)."
                    )

                    self.save_components()
                    return False

        # Fuzzy matching to check for near duplicates.
        close_matches = difflib.get_close_matches(new_part_number, existing_parts, n=1, cutoff=0.8)
        if close_matches:
            response = messagebox.askyesno(
                "Possible Duplicate",
                f"Did you mean '{close_matches[0]}' instead of '{new_part_number}'?"
            )
            if response:
                for comp in existing_components:
                    if comp.get("part_info", {}).get("part_number", "").strip().lower() == close_matches[0]:
                        try:
                            existing_count = int(comp["part_info"].get("count", 0))
                        except ValueError:
                            existing_count = 0
                        updated_count = existing_count + new_count
                        comp["part_info"]["count"] = updated_count

                        messagebox.showinfo("Found Duplicate", f"Component {comp['part_info']['part_number']} already exists.\nAdded {comp['part_info']['count']} units.")
                        loc = comp["part_info"]["location"]
                        self.ledControl.set_led_on(loc, 0, 255, 0)
                        messagebox.showinfo("Fill Vial", f"Fill vial at {loc}.")

                        self.log_change(
                            f"Updated component '{close_matches[0]}' count from {existing_count} to {updated_count} (matched '{new_part_number}')."
                        )
                        self.save_components()
                        return False

        # No duplicate found.
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
    
    def parse_bom(self, file_path):
        """
        Read a BOM CSV, drop any rows with an empty Part column
        or a “Total” footer, and annotate each row with:
           - found:   True/False
           - location
           - current_count
        Returns a list of dicts ready for display.
        """
        bom_list = []
        # adjust delimiter or encoding if needed
        with open(file_path, newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header line
            for cols in reader:
                # assume columns: Part, Digikey#, Manufacturer#, Price, # of Parts
                if len(cols) < 5:
                    continue
                part, digikey, manufacturer, price, qty = [c.strip() for c in cols[:5]]
                # skip blank part rows
                if not part:
                    continue
                # stop at a “Total” row if they label it in Part
                if part.lower().startswith("total"):
                    break

                # look up this digikey in inventory
                found = False
                location = None
                current_count = None
                for comp in self.components:
                    pn = comp["part_info"]["part_number"].strip().lower()
                    if pn == digikey.lower():
                        found = True
                        location = comp["part_info"].get("location")
                        try:
                            current_count = int(comp["part_info"].get("count", 0))
                        except ValueError:
                            current_count = None
                        break

                bom_list.append({
                    "part":          part,
                    "digikey":       digikey,
                    "manufacturer":  manufacturer,
                    "price":         price,
                    "quantity":      qty,
                    "found":         found,
                    "location":      location,
                    "current_count": current_count
                })

        return bom_list

    def process_bom_out(self, bom_list, board_name):
        """
        For each BOM row (dict with "digikey", "quantity", "found"):
        - If count < needed, skip subtraction and status "Out of Stock"
        - Else subtract and status "Updated"
        """
        results = []
        for row in bom_list:
            digikey = row.get("digikey", "").strip()
            try:
                quantity_used = int(row.get("quantity", 0))
            except ValueError:
                quantity_used = 0

            if row.get("found"):
                for comp in self.components:
                    if comp["part_info"].get("part_number","").strip().lower() == digikey.lower():
                        try:
                            current = int(comp["part_info"].get("count",0))
                        except ValueError:
                            current = 0

                        if current < quantity_used:
                            # OUT OF STOCK — no subtraction
                            results.append({
                                "part": digikey,
                                "remaining": current,
                                "status": "Out of Stock"
                            })
                        else:
                            new_count = current - quantity_used
                            comp["part_info"]["count"] = new_count
                            comp["metadata"]["in_use"] = f"Used for {board_name}"
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

        self.save_components()
        return results

    def process_returned_vials(self, bom_list, additional_usage):
        """
        Processes returned vials after checkout.

        For each BOM row, locate the corresponding component in the catalogue (self.components)
        by matching the digikey (part number), subtract the additional usage from its count,
        and update the metadata 'in_use' field to "Available". Then save the updated catalogue.

        Parameters:
            bom_list (list): A list of BOM row dictionaries, each with at least the keys "digikey" and "location".
            additional_usage (dict): A mapping from a unique component identifier (e.g., digikey)
                                    to the number of additional components used (as an int).

        Returns:
            list: A list of result dictionaries containing the part identifier, updated count,
                additional used, and status.
        """
        results = []
        for row in bom_list:
            digikey = row.get("digikey", "").strip()
            additional = additional_usage.get(digikey, 0)
            found = False

            # Locate the component in the catalogue
            for comp in self.components:
                comp_digikey = comp.get("part_info", {}).get("part_number", "").strip()
                if comp_digikey.lower() == digikey.lower():
                    found = True
                    try:
                        current_count = int(comp["part_info"].get("count", 0))
                    except ValueError:
                        current_count = 0

                    new_count = current_count - additional
                    comp["part_info"]["count"] = new_count

                    # Update the metadata: set "in_use" to "Available"
                    if "metadata" in comp:
                        comp["metadata"]["in_use"] = "Available"
                    else:
                        comp["metadata"] = {"in_use": "Available"}

                    results.append({
                        "part": digikey,
                        "remaining": new_count,
                        "additional_used": additional,
                        "status": "Returned"
                    })
                    break

            if not found:
                results.append({
                    "part": digikey,
                    "remaining": "N/A",
                    "additional_used": additional,
                    "status": "Component not found in catalogue"
                })

        # Save the updated catalogue to file.
        self.save_components()
        return results

    def checkout(self, part_number: str, qty: int):
        """
        Attempt to subtract `qty` from the component with `part_number`.
        Returns a dict:
          {
            "success": bool,
            "message": str,
            "location": str or None,
            "new_count": int or None
          }
        """
        key = part_number.strip().lower()
        # find component
        for comp in self.components:
            if comp["part_info"]["part_number"].strip().lower() == key:
                break
        else:
            return {
                "success": False,
                "message": f"Component '{part_number}' not found.",
                "location": None,
                "new_count": None
            }

        # parse current count
        try:
            current = int(comp["part_info"].get("count", 0))
        except ValueError:
            return {
                "success": False,
                "message": f"Invalid count for '{part_number}'.",
                "location": None,
                "new_count": None
            }

        # validate qty
        if qty <= 0:
            return {
                "success": False,
                "message": "Quantity must be positive.",
                "location": None,
                "new_count": current
            }
        if qty > current:
            return {
                "success": False,
                "message": "Not enough components in stock.",
                "location": comp["part_info"].get("location"),
                "new_count": current
            }

        # perform checkout
        new_count = current - qty
        comp["part_info"]["count"] = new_count
        self.save_components()

        return {
            "success":   True,
            "message":   f"Checked out {qty}× '{part_number}'. New count: {new_count}.",
            "location":  comp["part_info"].get("location"),
            "new_count": new_count
        }

    def undo_delete(self):
        """
        Restores the last deleted component, if available.
        Returns True if successful, or False if there is nothing to undo.
        """
        if self.undo_stack:
            component, index = self.undo_stack.pop()
            # Insert the component back at its original index.
            if index >= len(self.components):
                self.components.append(component)
            else:
                self.components.insert(index, component)
            self.save_components()
            part_number = component["part_info"].get("part_number", "Unknown")
            self.log_change(f"Restored component at index {index} (Part Number: {part_number}).")
            return True
        return False

    def schedule_backup(self, interval_seconds=3600):
        """
        Schedules the backup_catalogue method to run every interval_seconds.
        Uses threading.Timer to perform the backup in a separate thread.
        """
        def backup_wrapper():
            now = datetime.datetime.now()
            inactivity = now - self.last_activity
            self.backup_catalogue()
            # Reschedule the next backup and check for inactivity
            if inactivity < datetime.timedelta(minutes=30):
                self.backup_catalogue()
                # Reschedule the next backup.
                threading.Timer(interval_seconds, backup_wrapper).start()
            else:
                print("Autobackup deactivated due to inactivity (no changes for over 30 minutes).")
        
        # Schedule the first backup
        threading.Timer(interval_seconds, backup_wrapper).start()

    def backup_catalogue(self):
        """
        Creates a backup copy of the current catalogue.
        The backup is stored in a "backups" folder in the same directory as the catalogue.
        The backup file is named with a timestamp appended.
        """
        catalogue_path = self.data_file
        backup_dir = os.path.join(os.path.dirname(catalogue_path), "backups")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(catalogue_path)
        name, ext = os.path.splitext(base)
        backup_filename = f"{name}_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        try:
            shutil.copy2(catalogue_path, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print("Error creating backup:", e)
