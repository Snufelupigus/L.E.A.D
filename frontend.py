from tkinter import Tk, Label, Entry, Button, Canvas, StringVar, OptionMenu,  Menu, Frame, Toplevel, messagebox, Scrollbar, LEFT, BOTH, RIGHT, Y,  END, Checkbutton, BooleanVar
from tkinter.ttk import Treeview, Combobox
from tkinter.messagebox import askyesno
from tkinter.filedialog import asksaveasfilename, askopenfilename
import webbrowser

class Frontend:
    def __init__(self, backend, digikeyAPI, ledControl):
        self.backend = backend
        self.digikeyAPI = digikeyAPI
        self.ledControl = ledControl
        self.current_frame = None

        # Initialize Tkinter window
        self.root = Tk()
        self.root.title("Component Catalogue")
        self.root.geometry("1250x750")
        self.create_menu()

        # Start with the home page
        self.show_home()

        self.root.mainloop()

    def create_menu(self):
        menu_bar = Menu(self.root)

        nav_menu = Menu(menu_bar, tearoff=0)
        nav_menu.add_command(label="Home", command=self.show_home)
        nav_menu.add_command(label="Search", command=self.show_search)
        nav_menu.add_command(label="Add", command=self.show_add)
        menu_bar.add_cascade(label="Navigation", menu=nav_menu)

        self.root.config(menu=menu_bar)

    def clear_frame(self):
        if self.current_frame is not None:
            self.current_frame.destroy()

    def show_home(self):
        self.clear_frame()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Display statistics
        Label(self.current_frame, text="Home - Statistics", font=("Arial", 16)).pack(pady=20)

        stats = self.backend.get_statistics()
        Label(self.current_frame, text=f"Total Parts: {stats['total_parts']}").pack(pady=10)
        Label(self.current_frame, text=f"Types of Parts: {', '.join(stats['types'])}").pack(pady=10)

            # Add a separator label before the low-stock table.
        Label(self.current_frame, text="Low Stock Items", font=("Arial", 16)).pack(pady=20)

        Button(self.current_frame, text="Export Low Stock Data", command=self.export_low_stock_data).pack(pady=10)

        Button(self.current_frame, text="Process BOM File", command=self.show_bom_file_window).pack(padx=10)

        # Create a Treeview to show low-stock items.
        low_stock_tree = Treeview(self.current_frame, columns=("Digikey", "Count", "LowStock", "ProductURL"), show="headings")
        low_stock_tree.heading("Digikey", text="Digikey Part #")
        low_stock_tree.heading("Count", text="Count")
        low_stock_tree.heading("LowStock", text="Low Stock Threshold")
        low_stock_tree.heading("ProductURL", text="Product URL")

        # Set column widths as desired (adjust pixel values as needed)
        low_stock_tree.column("Digikey", width=150, anchor="w")
        low_stock_tree.column("Count", width=100, anchor="center")
        low_stock_tree.column("LowStock", width=150, anchor="center")
        low_stock_tree.column("ProductURL", width=300, anchor="w")
        low_stock_tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Get low-stock components from the backend.
        low_stock_components = self.backend.get_low_stock_components()
        for comp in low_stock_components:
            part_number = comp["part_info"].get("part_number", "N/A")
            try:
                count = int(comp["part_info"].get("count", 0))
            except (ValueError, TypeError):
                count = 0
            low_stock_val = comp["metadata"].get("low_stock", "N/A")
            product_url = comp["metadata"].get("product_url", "N/A")
            low_stock_tree.insert("", "end", values=(part_number, count, low_stock_val, product_url))

        # Bind a double-click event on a row to open the product URL in a web browser.
        def open_product(event):
            selected_item = low_stock_tree.focus()
            if not selected_item:
                return
            values = low_stock_tree.item(selected_item, "values")
            if values and len(values) >= 4:
                url = values[3]
                if url and url != "N/A":
                    webbrowser.open(url)

        low_stock_tree.bind("<Double-Button-1>", open_product)

    def show_search(self):
        self.clear_frame()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.current_frame.columnconfigure(0, weight=0)
        self.current_frame.columnconfigure(1, weight=0)
        self.current_frame.columnconfigure(2, weight=0)

        Label(self.current_frame, text="Search Components", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=20, sticky="w")

        # Bind delete key, etc.
        Button(self.current_frame, text="Checkout", command=lambda: self.checkout_component(search_tree)).grid(row=3, column=1, pady=10)


        # Search bar
        Label(self.current_frame, text="Search:").grid(row=1, column=0, padx=10, pady=5, sticky= "w")
        search_entry = Entry(self.current_frame, width=40)
        search_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Table of components
        search_tree = Treeview(self.current_frame, columns=("Part Number", "Manufacturer Number", "Location", "Count", "Type"), show="headings")
        for col in search_tree["columns"]:
            search_tree.heading(col, text=col)
            search_tree.column(col, anchor="w")
        search_tree.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

        def update_search_results(event):
            query = search_entry.get().strip()
            components = self.backend.search_components(query)
            for row in search_tree.get_children():
                search_tree.delete(row)
            for comp in components:
                search_tree.insert("", "end", values=(comp["part_info"]["part_number"], comp["part_info"]["manufacturer_number"], comp["part_info"]["location"], comp["part_info"]["count"], comp["part_info"]["type"]))

        search_entry.bind("<KeyRelease>", update_search_results)

        search_tree.bind("<Double-Button-1>", lambda event: self.edit_component(search_tree))

        # Populate table initially with all components
        update_search_results(None)

        # Edit button
        Button(self.current_frame, text="Edit Component", command=lambda: self.edit_component(search_tree)).grid(row=3, column=0, columnspan=2, pady=10)

        # Bind delete key
        search_tree.bind("<Delete>", lambda event: self.delete_component(search_tree))

    def show_add(self):
        self.clear_frame()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

        Label(self.current_frame, text="Add New Component", font=("Arial", 16)).grid(row=0, column=0, columnspan=4, pady=20, sticky="w")

        fields = {
            "part_number": (
                Label(self.current_frame, text="Part Number:"),  # Label widget
                Entry(self.current_frame)              # Entry widget
            ),
            "manufacturer_number": (
                Label(self.current_frame, text="Manufacturer Number:"),
                Entry(self.current_frame)
            ),
            "location": (
                Label(self.current_frame, text="Location:"),
                Entry(self.current_frame, width=15)
            ),
            "count": (
                Label(self.current_frame, text="Number of Components:"),
                Entry(self.current_frame, width=15)
            ),
            "low_stock": (
                Label(self.current_frame, text="Low Stock Threshold:"),
                Entry(self.current_frame, width=15)
            )
        }

        self.current_frame.columnconfigure(0, weight=0)
        self.current_frame.columnconfigure(1, weight=0)
        self.current_frame.columnconfigure(2, weight=0)
        self.current_frame.columnconfigure(3, minsize=105, weight=0)
        self.current_frame.columnconfigure(4, weight=1)
        self.current_frame.columnconfigure(5, weight=1)

        """
        styled_column = Frame(
            self.current_frame,
            bd=2,  # Border width
            relief="groove",  # Border style (try: flat, raised, sunken, ridge, groove)
            bg="#ff0000"  # Background color
        )
        styled_column.grid(row=0, column=3, rowspan=10, sticky="nswe", padx=10, pady=10)
        """

        component_type_var = StringVar()
        component_type_var.set("Other")  # Default value

        component_types = [
            "Cable", "Capacitor", "Connector", "Crystal", "Diode", "Evaluation", "Hardware", "IC", "Inductor",
            "Kit", "LED", "Module", "Other", "Relay", "Resistor", "Sensor", "Switch", "Transformer", "Transistor"
        ]

        def update_autocomplete(event, combobox, options):
            """Dynamically filters dropdown based on user input."""
            typed_text = combobox.get().lower()  # Get the current text in the entry field
            if not typed_text:  # If empty, restore full options
                combobox['values'] = options
                return
            
            # Filter options that match typed text
            filtered_options = [option for option in options if typed_text in option.lower()]
            
            # Update dropdown options
            combobox['values'] = filtered_options

        for row, (key, (label_widget, entry_widget)) in enumerate(fields.items(), start=1):
            label_widget.grid(row=row, column=0, padx=5, pady=5, sticky="w")
            entry_widget.grid(row=row, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        fields["location"][0].grid(row=3, column=0, padx=5, pady=5, sticky="w")  # Label
        fields["location"][1].grid(row=3, column=1, padx=5, pady=5, sticky="w")

        fields["count"][0].grid(row=3, column=2, padx=5, pady=5, sticky="w")  # Label
        fields["count"][1].grid(row=3, column=3, padx=5, pady=5, sticky="w")
        
        fields["low_stock"][0].grid(row=4, column=2, padx=5, pady=5, sticky="w")  # Label
        fields["low_stock"][1].grid(row=4, column=3, padx=5, pady=5, sticky="w")

        Label(self.current_frame, text="Type of Component:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        Combobox(self.current_frame, textvariable=component_type_var, values=component_types, width=12).grid(row=4, column=1, padx=5, pady=5, sticky="w")
        #component_type_combobox.bind("<KeyRelease>", lambda event: update_autocomplete(event, component_type_combobox, component_types))

        def add_component():
            #component_data = {key: widget.get().strip() if isinstance(widget, Entry) else component_type_var.get() for key, (_, widget) in fields.items()}
            component_data = {key: entry_widget.get().strip() for key, (_, entry_widget) in fields.items()}

            if not component_data["part_number"]:
                messagebox.showerror("Error", "Part Number is required!")
                return
            try:
                component_data["count"] = int(component_data["count"])
            except ValueError:
                messagebox.showerror("Error", "Count must be an integer!")
                return
            try:
                component_data["low_stock"] = int(component_data["low_stock"])
            except ValueError:
                messagebox.showerror("Error", "Low Stock Threshold must be a number!")
                return
            
            if self.backend.check_duplicate(component_data)== False: 
                messagebox.showinfo("Found Duplicate:", component_data['part_number'])
                update_add_tree()
                
                for key, (_, widget) in fields.items():
                    if isinstance(widget, Entry):
                        widget.delete(0, END)
                    else:
                        component_type_var.set("Other")
                return
            
            fetch_digikey_data(self)
        
        def fetch_digikey_data(self, part_number=None):
            if part_number:
                response = self.digikeyAPI.fetch_part_details(part_number["part_number"])
                response["part_info"]["count"] = part_number["count"]
                response["metadata"]["low_stock"] = part_number["low_stock"]
                print(response)
                self.backend.add_component(response)
                messagebox.showinfo("Success", "Component added successfully!")
            else:
                component_data = {key: entry_widget.get().strip() for key, (_, entry_widget) in fields.items()}
                print(component_data)

                if not component_data['part_number']:
                    messagebox.showerror("Error", "Part Number is required!")
                    return
                try:
                    component_data["count"] = int(component_data["count"])
                except ValueError:
                    messagebox.showerror("Error", "Count must be an integer!")
                    return
                
                if self.backend.check_duplicate(component_data)== False: 
                    messagebox.showinfo("Found Duplicate:", component_data['part_number'])
                    update_add_tree()

                    for key, (_, widget) in fields.items():
                        if isinstance(widget, Entry):
                            widget.delete(0, END)
                        else:
                            component_type_var.set("Other")
                    return
                
                response = self.digikeyAPI.fetch_part_details(component_data['part_number'])
                if response == None:
                    if askyesno("Not Found", "No Digikey Part Found, Add Anyway?"):
                        part_data = {
                            "part_info": {  # Essential inventory data
                                "part_number": component_data.get('part_number', "N/A"),
                                "manufacturer_number": component_data.get('manufacturerPartNumber', "N/A"),
                                "location": component_data.get('location',"N/A"),  # Default if not specified
                                "count": component_data.get('count', 0),  # Default count
                                "type": component_data.get('type', "N/A")  # Default type
                            },
                            "metadata": {  # Extra product details
                                "price": "N/A",  # Ensure numeric price
                                "low_stock": component_data.get("low_stock", "N/A"),
                                "description": "N/A",
                                "photo_url": "N/A",
                                "datasheet_url": "N/A",
                                "product_url": "N/A"
                            }
                        }

                        self.backend.add_component(part_data)
                        messagebox.showinfo("Success", "Component added successfully!")

                        for key, (_, widget) in fields.items():
                            if isinstance(widget, Entry):
                                widget.delete(0, END)
                            else:
                                component_type_var.set("Other")
                    else:
                        return
                else:
                    if response:
                        if part_number is None:
                            response["part_info"]["count"] = component_data["count"]
                            response["metadata"]["low_stock"] = component_data["low_stock"]
                            response['part_info']['location'] = component_data['location']

                        self.backend.add_component(response)
                        messagebox.showinfo("Success", "Component added successfully!")

                        for key, (_, widget) in fields.items():
                            if isinstance(widget, Entry):
                                widget.delete(0, END)
                            else:
                                component_type_var.set("Other")

            update_add_tree()
        
        def barcode_scan():
            """Opens a small window to scan barcode input."""
            barcode_window = Toplevel(self.root)
            barcode_window.title("Scan Barcode")
            barcode_window.geometry("300x150")
            barcode_window.resizable(False, False)

            Label(barcode_window, text="Scan Barcode", font=("Arial", 14)).pack(pady=20)

            barcode_var = StringVar()
            barcode_entry = Entry(barcode_window, textvariable=barcode_var, font=("Arial", 12), justify="center")
            barcode_entry.pack(pady=10)
            barcode_entry.focus_set()

            def process_barcode(event):
                """Detects barcode input and sends it to DigiKey API."""
                barcode = barcode_var.get().strip()
                barcode_window.destroy()  # Close the window

                extraInfo = Toplevel(self.root)
                extraInfo.title("Barcode Info")
                extraInfo.geometry("300x150")
                extraInfo.resizable(False, False)

                low_stock_var = StringVar(extraInfo)
                Label(extraInfo, text="Low Stock Threshold:").pack(pady=5)
                Entry(extraInfo, textvariable=low_stock_var, width=20).pack(pady=5, padx=15)

                extraInfo.focus_set()

                def low_stock_entry_handeling():
                    low_stock = int(low_stock_var.get())
                    extraInfo.destroy()  # Close the window
                    if barcode:
                        barcode_data=self.backend.barcode_decoder(barcode)
                        barcode_data['low_stock'] = low_stock

                        if self.backend.check_duplicate(barcode_data)== False: 
                            messagebox.showinfo("Found Duplicate:", barcode_data['part_number']) 
                            update_add_tree()
                            return

                        fetch_digikey_data(self, barcode_data)
                
                Button(extraInfo, text="Save", command= low_stock_entry_handeling).pack(pady= 5)

            # Bind the Enter key to process barcode input
            barcode_entry.bind("<Return>", process_barcode)

        def bulk_add(self):
            bulk_window = Toplevel(self.root)
            bulk_window.title("Bulk Barcode Add")
            bulk_window.geometry("800x600")
            
            # Create a container frame that holds the canvas and scrollbar.
            container = Frame(bulk_window)
            container.pack(fill=BOTH, expand=True)
            
            canvas = Canvas(container)
            canvas.pack(side=LEFT, fill=BOTH, expand=True)

            scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollbar.pack(side=RIGHT, fill=Y)
            
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            
            # The frame that will hold the bulk add rows.
            rows_frame = Frame(canvas)
            canvas.create_window((0, 0), window=rows_frame, anchor="nw")
            
            # List to store references to row widgets.
            self.bulk_rows = []

            def add_row():
                if not self.bulk_rows:
                    header_frame = Frame(rows_frame)
                    header_frame.pack(fill="x", padx=10, pady=5)
                    Label(header_frame, text="Barcode", width=40, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=0)
                    Label(header_frame, text="Low-Stock Threshold", width=20, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=20)

                row_frame = Frame(rows_frame, pady=5)
                row_frame.pack(fill="x", padx=10)
                
                barcode_entry = Entry(row_frame, width=40)
                barcode_entry.grid(row=0, column=0, padx=5)
                low_stock_entry = Entry(row_frame, width=20)
                low_stock_entry.grid(row=0, column=1, padx=5)
                
                # Save the row widget references
                self.bulk_rows.append({
                    "barcode": barcode_entry,
                    "low_stock": low_stock_entry,
                })
            # Button to add a new row
            add_row_button = Button(bulk_window, text="Add Row", command=add_row)
            add_row_button.pack(pady=5)
        
            # Add an initial row
            add_row()

            def finish_bulk():
                bulk_data = []
                for row in self.bulk_rows:
                    barcode_val = row["barcode"].get().strip()
                    low_stock_val = row["low_stock"].get().strip()
                    if barcode_val:  # only add rows with a barcode value
                        bulk_data.append({
                            "barcode": barcode_val,
                            "low_stock": low_stock_val,
                        })
                if bulk_data:
                    process_bulk_add(self, bulk_data)
                    bulk_window.destroy()
                else:
                    messagebox.showerror("Error", "No valid barcode rows entered.")

            finish_button = Button(bulk_window, text="Finish", command=finish_bulk)
            finish_button.pack(pady=10)

        def process_bulk_add(self, bulk_data):
            """
            For each entry in bulk_data (a list of dicts with keys 'barcode', 'type', and 'location'),
            call the Digikey API to fetch details, update the returned dictionary with the provided
            type and location, and then add the component to the backend.
            """
            for entry in bulk_data:
                barcode = entry["barcode"]
                low_stock = entry["low_stock"]

                # Call the API; note that fetch_part_details is part of your digikeyAPI.
                barcode_data=self.backend.barcode_decoder(barcode)
                print(barcode_data)

                #Check for duplicates
                if self.backend.check_duplicate(barcode_data)== False: 
                    messagebox.showinfo("Found Duplicate:", barcode_data['part_number'])

                else:
                    response = self.digikeyAPI.fetch_part_details(barcode_data["part_number"])

                    if response:
                        # Update the response with additional info from the bulk add form.
                        response["part_info"]["count"] = barcode_data["count"]
                        response["metadata"]["low_stock"] = low_stock or response["metadata"].get("low_stock", "N/A")
                        self.backend.add_component(response)
                    else:
                        messagebox.showerror("Error", f"Failed to fetch data for barcode: {barcode}")
            messagebox.showinfo("Success", "Bulk add completed!")
            update_add_tree()

        Button(self.current_frame, text="Add Component", command=add_component).grid(row=len(fields), column=0, columnspan=2, pady=5, padx=10, sticky= "w")
        Button(self.current_frame, text="Add Barcode", command=barcode_scan).grid(row=len(fields), column=5, columnspan=2, pady=5)
        Button(self.current_frame, text="Bulk Scan", command=lambda: bulk_add(self)).grid(row=len(fields)-1, column=5, columnspan=2, pady=5)

        self.root.bind("<Return>", lambda event: add_component())
        
        # Table of components
        add_tree = Treeview(self.current_frame, columns=("Part Number", "Manufacturer Number", "Location", "Count", "Type"), show="headings")
        
        for col in add_tree["columns"]:
            add_tree.heading(col, text=col)
            add_tree.column(col, anchor="w")
        add_tree.grid(row=len(fields) + 1, column=0, columnspan=6, sticky="nsew", padx=10, pady=10)

        def update_add_tree():
            for row in add_tree.get_children():
                add_tree.delete(row)
            for comp in self.backend.get_all_components():
                add_tree.insert("", "end", values=(comp["part_info"]["part_number"], comp["part_info"]["manufacturer_number"], comp["part_info"]["location"], comp["part_info"]["count"], comp["part_info"]["type"]))

        add_tree.bind("<Double-Button-1>", lambda event: self.edit_component(add_tree))

        update_add_tree()

        # Edit button
        Button(self.current_frame, text="Edit Component", command=lambda: self.edit_component(add_tree)).grid(row=len(fields), column=1, columnspan=1, pady=10, sticky="w")

        # Bind delete key
        add_tree.bind("<Delete>", lambda event: self.delete_component(add_tree))

    def edit_component(self, tree):
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "No component selected!")
            return

        index = int(tree.index(selected_item))
        component = self.backend.get_all_components()[index]

        edit_window = Toplevel(self.root)
        edit_window.title("Edit Component")
        edit_window.geometry("500x600")

        highlight_state = {"on": False}  # Track whether the LED is currently highlighted.
        def on_close():
            if highlight_state["on"]:
                self.ledControl.turn_off_led(component["part_info"]["location"])
            edit_window.destroy()
        edit_window.protocol("WM_DELETE_WINDOW", on_close)

        #Part Info Section
        fields = {}

        Label(edit_window, text="Part Information", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=5)

        for i, key in enumerate(["part_number", "manufacturer_number", "location", "count", "type"]):
            Label(edit_window, text=key.replace("_", " ").title() + ":").grid(row=i+1, column=0, padx=10, pady=5)
            entry = Entry(edit_window, width=30)
            entry.insert(0, str(component["part_info"][key]))
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
            fields[key] = entry

        # Metadata Section
        Label(edit_window, text="Metadata", font=("Arial", 12, "bold")).grid(row=8, column=0, columnspan=2, pady=5)

        metadata_fields = {}

        for i, key in enumerate(["price", "low_stock", "description", "photo_url", "datasheet_url", "product_url"]):
            Label(edit_window, text=key.replace("_", " ").title() + ":").grid(row=i+9, column=0, padx=10, pady=5)
            entry = Entry(edit_window, width=40)
            entry.insert(0, str(component["metadata"].get(key, "N/A")))
            entry.grid(row=i+9, column=1, padx=10, pady=5, sticky="ew")
            metadata_fields[key] = entry

        highlight_color = (0, 255, 0)
        def toggle_highlight():
            if not highlight_state["on"]:
                # Turn on the LED at the component's location.
                self.ledControl.set_led_on(component["part_info"]["location"], *highlight_color)
                highlight_button.config(text="Unhighlight")
                highlight_state["on"] = True
            else:
                # Turn off the LED.
                self.ledControl.turn_off_led(component["part_info"]["location"])
                highlight_button.config(text="Highlight")
                highlight_state["on"] = False

        highlight_button = Button(edit_window, text="Highlight", command=toggle_highlight)
        # Place the highlight button where it fits best (here we put it after metadata fields).
        highlight_button.grid(row=15, column=0, columnspan=2, pady=10)

        def save_changes():
            updated_data = {
                "part_info": {},
                "metadata": {}
            }
            # Save part_info fields
            for key, entry in fields.items():
                updated_data["part_info"][key] = entry.get().strip()
            if "count" in updated_data["part_info"]:
                try:
                    updated_data["part_info"]["count"] = int(updated_data["part_info"]["count"])
                except ValueError:
                    messagebox.showerror("Error", "Count must be an integer!")
                    return
            else:
                updated_data["part_info"]["count"] = 0  # Default if missing

            # Collect new metadata from the entry widgets
            new_metadata = {}
            metadata_changed = False
            for key, entry in metadata_fields.items():
                new_val = entry.get().strip()
                new_metadata[key] = new_val
                # Get the original value (convert to string in case it's not)
                original_val = str(component["metadata"].get(key, "N/A"))
                if new_val != original_val:
                    metadata_changed = True

            # If any metadata field was changed, ask the user to confirm
            if metadata_changed:
                if not askyesno("Confirm Metadata Change", "Metadata fields have been modified. Are you sure you want to save these changes?"):
                    return

            updated_data["metadata"] = new_metadata

            # Save the changes via the backend
            self.backend.edit_component(index, updated_data)
            messagebox.showinfo("Success", "Component updated successfully!")
            
            if highlight_state["on"]:
                self.ledControl.turn_off_led(component["part_info"]["location"])

            edit_window.destroy()

            # Refresh only the selected row in the TreeView
            tree.item(selected_item, values=(
                updated_data["part_info"]["part_number"],
                updated_data["part_info"]["manufacturer_number"],
                updated_data["part_info"]["location"],
                updated_data["part_info"]["count"],
                updated_data["part_info"]["type"]
            ))

        Button(edit_window, text="Save Changes", command=save_changes).grid(row=7, column=0, columnspan=2, pady=10)
        edit_window.bind("<Return>", lambda event: save_changes())

    def delete_component(self, tree):
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "No component selected!")
            return

        index = int(tree.index(selected_item))
        self.backend.delete_component(index)
        messagebox.showinfo("Success", "Component deleted successfully!")

        # Remove the selected row from TreeView
        tree.delete(selected_item)

    def export_low_stock_data(self):
        # Open a Save As dialog to get the file path
        file_path = asksaveasfilename(
            title="Export Low Stock Data",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            # User cancelled the dialog
            return

        # Retrieve low stock components from the backend.
        # (Ensure your backend has a get_low_stock_components() method that returns a list of components.)
        low_stock_components = self.backend.get_low_stock_components()

        # Build the file content as plain text.
        lines = []
        for comp in low_stock_components:
            part_number = comp["part_info"].get("part_number", "N/A")
            count = comp["part_info"].get("count", "N/A")
            low_stock_value = comp["metadata"].get("low_stock", "N/A")
            product_url = comp["metadata"].get("product_url", "N/A")
            # You can format the line as needed. Here’s one example:
            line = f"Part Number: {part_number} | Count: {count} | Low Stock: {low_stock_value} | URL: {product_url}"
            lines.append(line)
        file_content = "\n".join(lines)

        # Write the file content to the chosen file.
        try:
            with open(file_path, "w") as f:
                f.write(file_content)
            messagebox.showinfo("Export Successful", f"Low stock data exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export file:\n{e}")

    def show_bom_file_window(self):
        bom_win = Toplevel(self.root)
        bom_win.title("BOM File Input")
        bom_win.geometry("400x200")
        bom_win.resizable(False, False)
        
        Label(bom_win, text="Select a BOM file to process:", font=("Arial", 12)).pack(pady=20)
        Button(bom_win, text="Select File", command=lambda: self.process_bom_file(bom_win)).pack(pady=10)

        bom_win.protocol("WM_DELETE_WINDOW", lambda: (self.ledControl.turn_off_recent(), bom_win.destroy()))

    def process_bom_file(self, parent_win):
        file_path = askopenfilename(
            title="Select BOM File",
            filetypes=[("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            messagebox.showerror("Error", "No file selected!")
            return

        try:
            with open(file_path, "r") as f:
                lines = f.read().strip().splitlines()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")
            return

        bom_list = []
        # Assuming each line is CSV with 5 columns:
        # Part, Digikey #, Manufacturer #, Price, # of Parts
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue
            bom_list.append({
                "part": parts[0],
                "digikey": parts[1],
                "manufacturer": parts[2],
                "price": parts[3],
                "quantity": parts[4]
            })

        if not bom_list:
            messagebox.showerror("Error", "No valid BOM rows found in the file!")
            return

        # For each BOM row, check if the component exists in the catalogue.
        for row in bom_list:
            found = False
            for comp in self.backend.get_all_components():
                comp_digikey = comp["part_info"].get("part_number", "").strip()
                if comp_digikey.lower() == row["digikey"].lower():
                    found = True
                    row["location"] = comp["part_info"].get("location", None)
                    try:
                        row["current_count"] = int(comp["part_info"].get("count", 0))
                    except ValueError:
                        row["current_count"] = 0
                    break
            row["found"] = found

        parent_win.destroy()  # Close the BOM file input window.

        for row in bom_list:
            if row.get("found") and row.get("location"):
                # Light that LED with, say, green color (0,255,0)
                self.ledControl.set_led_on(row["location"], 0, 255, 0)

        self.show_bom_preview(bom_list)

    def show_bom_preview(self, bom_list):
        preview_win = Toplevel(self.root)
        preview_win.title("BOM Preview")
        preview_win.geometry("600x400")

        preview_win.protocol("WM_DELETE_WINDOW", lambda: (self.ledControl.turn_off_recent(), preview_win.destroy()))
        
        # Create a BooleanVar for the Checkbutton.
        highlight_all = BooleanVar()
        highlight_all.set(False)  # Default: highlight only the selected component.

        # Create a Checkbutton to allow the user to toggle highlighting.
        chk = Checkbutton(preview_win, text="Highlight All Components", variable=highlight_all, command=lambda: update_highlighting())
        chk.pack(anchor="w", padx=10, pady=5)

        tree = Treeview(preview_win, columns=("Digikey", "Quantity", "Found", "Current Count"), show="headings")
        tree.heading("Digikey", text="Digikey Part #")
        tree.heading("Quantity", text="# Used")
        tree.heading("Found", text="Found")
        tree.heading("Current Count", text="Current Count")
        
        tree.column("Digikey", width=150, anchor="w")
        tree.column("Quantity", width=80, anchor="center")
        tree.column("Found", width=80, anchor="center")
        tree.column("Current Count", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        for row in bom_list:
            tree.insert("", "end", values=(
                row["digikey"], row["quantity"], 
                "Yes" if row.get("found") else "No", 
                row.get("current_count", "N/A")
            ))

        def update_highlighting():
            """Update LED highlighting based on the checkbox and current selection."""
            # First, turn off any previously highlighted LEDs.
            self.ledControl.turn_off_recent()
            
            if highlight_all.get():
                # Highlight every BOM row that is found and has a valid location.
                for row in bom_list:
                    if row.get("found") and row.get("location"):
                        self.ledControl.set_led_on(row["location"], 0, 255, 0)
            else:
                # Highlight only the currently selected row.
                selected = tree.selection()
                if selected:
                    # Get the Digikey part number from the selected row.
                    item = tree.item(selected[0], "values")
                    selected_digikey = item[0]
                    # Find the corresponding row in bom_list.
                    for row in bom_list:
                        if row["digikey"].lower() == selected_digikey.lower():
                            if row.get("found") and row.get("location"):
                                self.ledControl.set_led_on(row["location"], 0, 255, 0)
                            break
        
        def on_tree_select(event):
            """When the selection changes in the Treeview, update highlighting (if not highlighting all)."""
            if not highlight_all.get():
                update_highlighting()
        
        # Bind the selection event to update highlighting.
        tree.bind("<<TreeviewSelect>>", on_tree_select)
        
        def process_bom_callback():
            # Call backend.process_bom to subtract quantities from found items.
            results = self.backend.process_bom(bom_list)
            preview_win.destroy()
            self.ledControl.turn_off_recent()
            self.show_bom_results(results)
            
        Button(preview_win, text="Consume Components?", command=process_bom_callback).pack(pady=10)

    def show_bom_results(self, results):
        result_win = Toplevel(self.root)
        result_win.title("BOM Processing Results")
        result_win.geometry("600x400")
        
        result_tree = Treeview(result_win, columns=("Part", "Remaining", "Status"), show="headings")
        result_tree.heading("Part", text="Digikey Part #")
        result_tree.heading("Remaining", text="Remaining Count")
        result_tree.heading("Status", text="Status")
        result_tree.column("Part", width=150, anchor="w")
        result_tree.column("Remaining", width=100, anchor="center")
        result_tree.column("Status", width=150, anchor="center")
        result_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        for res in results:
            result_tree.insert("", "end", values=(res["part"], res["remaining"], res["status"]))
        
        messagebox.showinfo("BOM Processed", "BOM processing complete. Inventory has been updated.")


    def checkout_component(self, tree):
        # Ensure a part is selected in the Treeview.
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "No component selected!")
            return

        # Retrieve selected component details.
        values = tree.item(selected_item, "values")
        # Expected values order: [Part Number, Manufacturer Number, Location, Count, Type]
        part_number = values[0]
        location = values[2]
        try:
            current_count = int(values[3])
        except ValueError:
            current_count = 0

        # Create a window to ask for the quantity to remove.
        checkout_win = Toplevel(self.root)
        checkout_win.title("Checkout Part")
        checkout_win.geometry("300x150")
        Label(checkout_win, text="How many components to remove?").pack(pady=10)
        qty_entry = Entry(checkout_win)
        qty_entry.pack(pady=5)
        qty_entry.focus_set()

        def submit_qty():
            qty_str = qty_entry.get().strip()
            try:
                qty = int(qty_str)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid integer")
                return
            if qty <= 0:
                messagebox.showerror("Error", "Quantity must be positive")
                return
            if qty > current_count:
                messagebox.showerror("Error", "Not enough components in stock")
                return

            checkout_win.destroy()  # Close the quantity entry window

            # Find the component index in the backend by part number.
            comp_index = None
            components = self.backend.get_all_components()
            for i, comps in enumerate(components):
                if comps["part_info"].get("part_number", "").strip().lower() == part_number.lower():
                    comp_index = i
                    break
            if comp_index is None:
                messagebox.showerror("Error", "Component not found in backend")
                return

            # Update the component's count.
            comps = components[comp_index]
            new_count = current_count - qty
            comps["part_info"]["count"] = new_count

            # Light up the LED for the component's location.
            # (Assumes the location code is stored in the tree as shown.)
            self.ledControl.set_led_on(location, 0, 255, 0)  # For example, green

            # Pop up a window that informs the user the component is lit.
            lit_win = Toplevel(self.root)
            lit_win.title("Component Lit Up")
            lit_win.geometry("300x150")
            Label(lit_win, text=f"Component {part_number} at {location} is lit up.").pack(pady=20)
            Label(lit_win, text="Press Enter or click OK when replaced.").pack(pady=10)
            
            def confirm_replaced(event=None):
                lit_win.destroy()
                # Ask for confirmation that the vial has been replaced.
                if messagebox.askyesno("Confirm Replacement", "Have you replaced the vial?"):
                    # Turn off the LED for that specific location.
                    self.ledControl.turn_off_led(location)
                    # Update the backend with the new count.
                    self.backend.edit_component(comp_index, comps)
                    messagebox.showinfo("Success", f"Checkout complete.\nNew count: {new_count}")
                    # Refresh the treeview.
                    for row in tree.get_children():
                        tree.delete(row)
                    for comp in self.backend.get_all_components():
                        tree.insert("", "end", values=(
                            comp["part_info"]["part_number"],
                            comp["part_info"]["manufacturer_number"],
                            comp["part_info"]["location"],
                            comp["part_info"]["count"],
                            comp["part_info"]["type"]
                        ))

            
            Button(lit_win, text="OK", command=confirm_replaced).pack(pady=10)
            lit_win.bind("<Return>", confirm_replaced)
            lit_win.protocol("WM_DELETE_WINDOW", lambda: (self.ledControl.turn_off_recent(), lit_win.destroy()))
            
        Button(checkout_win, text="Submit", command=submit_qty).pack(pady=10)
