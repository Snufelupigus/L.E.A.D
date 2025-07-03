from tkinter import Tk, Label, Entry, Button, Canvas, StringVar, simpledialog, OptionMenu,  Menu, Frame, Toplevel, messagebox, Scrollbar, LEFT, BOTH, RIGHT, Y,  END, Checkbutton, BooleanVar, TOP, X
from tkinter.ttk import Treeview, Combobox
from tkinter.messagebox import askyesno
from tkinter.filedialog import asksaveasfilename, askopenfilename

import os
import signal

from PIL import Image, ImageTk

import time
from io import BytesIO
import webbrowser

class Frontend:
    def __init__(self, backend, digikeyAPI, ledControl, imageCache):
        self.backend = backend
        self.digikeyAPI = digikeyAPI
        self.ledControl = ledControl
        self.imageCache = imageCache
        self.current_frame = None
        self.current_menu = None
        self.test_mode = False
        self.last_highlighted_location = None

        # Initialize Tkinter window
        self.root = Tk()
        self.root.title("Component Catalogue")
        self.root.geometry("1250x750")
        self.root.state('zoomed')

        # better autoscaling
        self.root.grid_rowconfigure( 0, weight=1 )
        self.root.grid_columnconfigure( 0, weight=1 )
        self.root.minsize(1000, 600)

        self.create_menu()
        self.root.focus_force()

        self.root.bind("<Control-Alt-t>", self.toggle_test_mode)
        self.default_bg = self.root.cget("bg")

        self.root.protocol("WM_DELETE_WINDOW", self.__exit__)

        # Start with the home page
        self.show_home()

        self.root.mainloop()

    def __exit__(self):
        os.kill(os.getpid(), signal.SIGTERM)

    def switch_menu(self, menu_func):
        """Helper to switch menus and record the current menu"""
        self.currrent_menu = menu_func
        menu_func()

    def create_menu(self):
        menu_bar = Menu(self.root)

        nav_menu = Menu(menu_bar, tearoff=0)
        nav_menu.add_command(label="Home", command=lambda: self.switch_menu(self.show_home))
        nav_menu.add_command(label="Search", command=lambda: self.switch_menu(self.show_search))
        nav_menu.add_command(label="Add", command=lambda: self.switch_menu(self.show_add))
        menu_bar.add_cascade(label="Navigation", menu=nav_menu)

        self.root.config(menu=menu_bar)

        edit_menu = Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo_last_deletion)
        #edit_menu.add_command(label="Redo", command=self.show_search)
        #edit_menu.add_command(label="Edit", command=self.show_add)
        menu_bar.add_cascade(label="Tools", menu=edit_menu)

        self.root.config(menu=menu_bar)

    def toggle_test_mode(self, event=None):
        self.test_mode = not self.test_mode
        
        current_dir = os.path.dirname(self.backend.data_file)

        if self.test_mode:
            self.backend.data_file = os.path.join(current_dir, "test_catalogue.json")
            messagebox.showinfo("Test Mode", "Test Mode ENABLED")
            self.root.config(bg="red")
        else:
            self.backend.data_file = os.path.join(current_dir, "component_catalogue.json")
            messagebox.showinfo("Test Mode", "Test Mode DISABLED")
            self.root.config(bg=self.default_bg)

        self.backend.load_components()
    
        # Refresh the current menu. If current_menu is not set, default to home.
        if hasattr(self, 'current_menu') and self.current_menu:
            self.current_menu()
        else:
            self.show_home()

    def clear_frame(self):
        self.ledControl.turn_off_recent()
        if self.current_frame is not None:
            self.current_frame.unbind_all("<Return>")
            self.current_frame.destroy()

        # Create new frame with proper configuration
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configure the main frame for responsive behavior
        # self.current_frame.grid_columnconfigure(0, weight=0)  # Labels don't expand
        # self.current_frame.grid_columnconfigure(1, weight=0)  # Entry fields don't expand  
        # self.current_frame.grid_columnconfigure(2, weight=0)  # Buttons don't expand
        # self.current_frame.grid_columnconfigure(3, weight=1)  # Details frame expands
        # self.current_frame.grid_columnconfigure(4, weight=1)  # Details frame expands



    def show_home(self):
        self.clear_frame()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Display statistics
        Label(self.current_frame, text="Home - Statistics", font=("Arial", 16)).pack(pady=20)

        stats = self.backend.get_statistics()
        Label(self.current_frame, text=f"Total Parts: {stats['total_parts']}").pack(pady=10)
        Label(self.current_frame, text=f"Types of Parts: {', '.join(stats['types'])}").pack(pady=10)

        Label(self.current_frame, text="Build A Board", font=("Arial", 16)).pack(pady=20)

        buttons_frame = Frame(self.current_frame)
        buttons_frame.pack(side=TOP, fill=X, padx=10, pady=5)

        center_frame = Frame(buttons_frame)
        center_frame.pack(expand=True)

        Button(center_frame, text="Checkout From BOM", command=lambda: self.process_bom_file("out")).pack(side=LEFT, padx=10)
        Button(center_frame, text="Check In From BOM", command=lambda: self.process_bom_file("in")).pack(side=LEFT, padx=10)

        Label(self.current_frame, text="Low Stock Items", font=("Arial", 16)).pack(pady=20)

        Button(self.current_frame, text="Export Low Stock Data", command=self.export_low_stock_data).pack(pady=10)

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
        # Initialize class attributes for widget references
        self.results_label = None
        self.action_button_frame = None
        
        self.clear_frame()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Configure main grid - 5 rows, 2 columns
        self.current_frame.grid_rowconfigure(0, weight=0) # Search label - fixed
        self.current_frame.grid_rowconfigure(1, weight=0) # Search entry - fixed  
        self.current_frame.grid_rowconfigure(2, weight=1) # Details section - expands
        self.current_frame.grid_rowconfigure(3, weight=1) # Table section - expands
        self.current_frame.grid_rowconfigure(4, weight=0) # Buttons - fixed
        
        self.current_frame.grid_columnconfigure(0, weight=1) # Left column expands
        self.current_frame.grid_columnconfigure(1, weight=1) # Right column expands

        # ========== ROW 0: Search Label ==========
        Label(
            self.current_frame, 
            text="Search Components",
            font=("Arial", 16)
        ).grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")

        # ========== ROW 1: Search Entry ==========

        search_entry = Entry(self.current_frame, width=80, font=("Arial", 12))
        search_entry.grid(row=1, column=0, columnspan=2, pady=(0, 15), sticky="ew")

        # ========== ROW 2: Details Section ==========
        
        # Left Column: Part Info and Metadata (stacked vertically)
        left_column = Frame(self.current_frame)
        left_column.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        
        # Configure left column - 2 rows for Part Info and Metadata
        left_column.grid_rowconfigure(0, weight=1)  # Part Info section
        left_column.grid_rowconfigure(1, weight=1)  # Metadata section  
        left_column.grid_columnconfigure(0, weight=1)

        # Part Info Section
        part_info_frame = Frame(left_column, bd=2, relief="groove", padx=10, pady=10)
        part_info_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        part_info_frame.grid_rowconfigure(1, weight=1)
        part_info_frame.grid_columnconfigure(0, weight=1)
        
        Label(
            part_info_frame, 
            text="Part Info", 
            font=("Arial", 12, "bold"), 
            bg="lightgrey"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self.part_info_content = Frame(part_info_frame)
        self.part_info_content.grid(row=1, column=0, sticky="nsew")

        # Metadata Section  
        metadata_frame = Frame(left_column, bd=2, relief="groove", padx=10, pady=10)
        metadata_frame.grid(row=1, column=0, sticky="nsew", pady=0 )
        metadata_frame.grid_rowconfigure(1, weight=1)
        metadata_frame.grid_columnconfigure(0, weight=1)
        
        Label(
            metadata_frame, 
            text="Metadata", 
            font=("Arial", 12, "bold"), 
            bg="lightgrey"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self.metadata_content = Frame(metadata_frame)
        self.metadata_content.grid(row=1, column=0, sticky="nsew")

        # Right Column: Image Section
        image_frame = Frame(self.current_frame, bd=2, relief="groove", padx=10, pady=10)
        image_frame.grid(row=2, column=1, sticky="nsew", padx=(0, 10))
        image_frame.grid_rowconfigure(1, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)
        
        Label(
            image_frame, 
            text="Image", 
            font=("Arial", 12, "bold"), 
            bg="lightgrey"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.image_content = Frame(image_frame)
        self.image_content.grid(row=1, column=0, sticky="nsew")

        # Default content for empty state
        Label(
            self.part_info_content, 
            text="Select Component to view part information.",
            justify="center",
            fg="gray"
        ).pack(expand=True)
        
        Label(
            self.metadata_content, 
            text="Select Component to view metadata.",
            justify="center",
            fg="gray"
        ).pack(expand=True)
        
        Label(
            self.image_content, 
            text="Select Component to view image.",
            justify="center",
            fg="gray"
        ).pack(expand=True)

        # ========== ROW 3: Component Table ==========
        
        # Table container
        table_container = Frame(self.current_frame)
        table_container.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=0, pady=(15, 0))
        
        # Configure table container internal grid
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Column options for the table
        columns_options = {
            "Part Number": {"width": 150, "anchor": "w"},
            "Manufacturer Number": {"width": 150, "anchor": "w"},
            "Location": {"width": 80, "anchor": "center"},
            "Count": {"width": 80, "anchor": "center"},
            "Type": {"width": 200, "anchor": "w"}
        }

        # Create the treeview
        self.search_tree = Treeview(
            table_container,
            columns=list(columns_options.keys()),
            show="headings",
            height=10
        )

        # Configure columns
        for col in columns_options:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, **columns_options[col])

        # Add scrollbar for table
        table_scrollbar = Scrollbar(table_container, orient="vertical", command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=table_scrollbar.set)
        
        # Place treeview and scrollbar in container
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        table_scrollbar.grid(row=0, column=1, sticky="ns")

        # ========== SEARCH FUNCTIONALITY ==========
        
        # Create search state storage
        self.search_results = []
        self.current_selection = 0
        
        def update_search_results(event):
            query = search_entry.get().strip()
            self.search_results = self.backend.search_components(query)
            
            # Update the table
            for row in self.search_tree.get_children():
                self.search_tree.delete(row)
            for comp in self.search_results:
                self.search_tree.insert("", "end", values=(
                    comp["part_info"]["part_number"],
                    comp["part_info"]["manufacturer_number"],
                    comp["part_info"]["location"],
                    comp["part_info"]["count"],
                    comp["part_info"]["type"]
                ))
            
            # Display search results count
            if hasattr(self, 'results_label') and self.results_label:
                self.results_label.destroy()
                
            results_text = f"Found {len(self.search_results)} components"
            if query:
                results_text += f" matching '{query}'"
                
            self.results_label = Label(
                self.current_frame, 
                text=results_text,
                font=("Arial", 10),
                fg="blue"
            )
            self.results_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(25, 0))
            
            # Auto-select first result if available
            if self.search_results:
                # Select first item in table
                first_item = self.search_tree.get_children()[0]
                self.search_tree.selection_set(first_item)
                self.search_tree.focus(first_item)
                self.show_component_details_from_table()
            else:
                self.clear_component_details()

        # Bind events
        search_entry.bind("<KeyRelease>", update_search_results)
        
        # Bind table selection to update details
        self.search_tree.bind("<<TreeviewSelect>>", lambda event: self.show_component_details_from_table())
        self.search_tree.bind("<Double-Button-1>", lambda event: self.edit_component(self.search_tree))
        self.search_tree.bind("<Delete>", lambda event: self.delete_component(self.search_tree))
        
        # Focus on search entry
        search_entry.focus_set()

        # Initial population
        update_search_results(None)


    def show_component_details_from_table(self):
        """Show component details when table selection changes"""
        selected = self.search_tree.selection()
        if not selected:
            self.clear_component_details()
            return

        item = self.search_tree.item(selected[0], "values")
        part_number = item[0]

        # Find the component in the backend
        component = next((comp for comp in self.backend.get_all_components()
                        if comp["part_info"]["part_number"].strip().lower() == part_number.strip().lower()), None)
        
        if not component:
            return

        # Handle LED highlighting
        new_location = component["part_info"].get("location", "").strip()
        if hasattr(self, 'last_highlighted_location') and self.last_highlighted_location and self.last_highlighted_location != new_location:
            self.ledControl.turn_off_led(self.last_highlighted_location)

        if new_location:
            self.ledControl.set_led_on(new_location, 0, 255, 0)
            self.last_highlighted_location = new_location

        # Clear previous content
        for widget in self.part_info_content.winfo_children():
            widget.destroy()
        for widget in self.metadata_content.winfo_children():
            widget.destroy()
        for widget in self.image_content.winfo_children():
            widget.destroy()

        # Populate Part Info
        row_idx = 0
        for key, value in component["part_info"].items():
            field_frame = Frame(self.part_info_content)
            field_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            field_frame.grid_columnconfigure(1, weight=1)
            
            Label(
                field_frame,
                text=f"{key.replace('_', ' ').title()}:",
                anchor="w",
                font=("Arial", 9, "bold")
            ).grid(row=0, column=0, sticky="nw", padx=(0, 5))
            
            Label(
                field_frame,
                text=f"{value}",
                anchor="w",
                wraplength=200,
                justify="left"
            ).grid(row=0, column=1, sticky="ew")
            row_idx += 1

        # Populate Metadata
        metadata_fields = ["price", "low_stock", "description", "in_use"]
        row_idx = 0
        for key in metadata_fields:
            value = component["metadata"].get(key, "N/A")
            
            field_frame = Frame(self.metadata_content)
            field_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            field_frame.grid_columnconfigure(1, weight=1)
            
            Label(
                field_frame,
                text=f"{key.replace('_', ' ').title()}:",
                anchor="w",
                font=("Arial", 9, "bold")
            ).grid(row=0, column=0, sticky="nw", padx=(0, 5))
            
            if key == "description":
                value_label = Label(
                    field_frame,
                    text=str(value),
                    anchor="w",
                    wraplength=200,
                    justify="left"
                )
            else:
                value_label = Label(
                    field_frame,
                    text=str(value),
                    anchor="w"
                )
            
            value_label.grid(row=0, column=1, sticky="ew")
            row_idx += 1

        # Load and display image
        self.load_component_image_new(component)

        # Add action buttons
        self.create_action_buttons(component)


    def load_component_image_new(self, component):
        """Load and display component image in the new layout"""
        # Create fixed-size container for image
        image_container = Frame(self.image_content, width=200, height=200, bg="white")
        image_container.pack(expand=True, fill="both", padx=10, pady=10)
        image_container.pack_propagate(False)

        try:
            image_entry = self.digikeyAPI.fetch_image_data(
                photo_url=component.get("metadata", {}).get("photo_url", ""),
                part_number=component.get("part_info", {}).get("part_number", "")
            )
            if image_entry and image_entry.image:
                pil_image = Image.open(BytesIO(image_entry.image))
                pil_image.thumbnail((180, 180), Image.Resampling.LANCZOS)
                tk_image = ImageTk.PhotoImage(pil_image)
                
                image_label = Label(image_container, image=tk_image)
                image_label.image = tk_image
                image_label.pack(expand=True)
            else:
                Label(
                    image_container, 
                    text="No Image\nAvailable", 
                    justify="center", 
                    font=("Arial", 12)
                ).pack(expand=True)
        except Exception as e:
            Label(
                image_container, 
                text=f"Image Error:\n{str(e)[:50]}...", 
                justify="center", 
                font=("Arial", 8), 
                fg="red"
            ).pack(expand=True)


    def create_action_buttons(self, component):
        """Create action buttons for the selected component"""
        # Remove existing button frame
        if hasattr(self, 'action_button_frame') and self.action_button_frame:
            self.action_button_frame.destroy()

        # Create new button frame
        self.action_button_frame = Frame(self.current_frame)
        self.action_button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        Button(
            self.action_button_frame, 
            text="Edit Component", 
            command=lambda: self.edit_component(self.search_tree)
        ).pack(side="left", padx=5)
        
        Button(
            self.action_button_frame, 
            text="Checkout", 
            command=lambda: self.checkout_component(self.search_tree)
        ).pack(side="left", padx=5)
        
        highlight_state = {"on": False}
        def toggle_highlight():
            location = component["part_info"]["location"]
            if not highlight_state["on"]:
                self.ledControl.set_led_on(location, 0, 255, 0)
                highlight_btn.config(text="Turn Off", relief='sunken')
                highlight_state["on"] = True
            else:
                self.ledControl.turn_off_led(location)
                highlight_btn.config(text="Highlight", relief='raised')
                highlight_state["on"] = False

        highlight_btn = Button(self.action_button_frame, text="Highlight", command=toggle_highlight)
        highlight_btn.pack(side="left", padx=5)


    def clear_component_details(self):
        """Clear all component details and show default state"""
        for widget in self.part_info_content.winfo_children():
            widget.destroy()
        for widget in self.metadata_content.winfo_children():
            widget.destroy()
        for widget in self.image_content.winfo_children():
            widget.destroy()
            
        Label(
            self.part_info_content, 
            text="No components found", 
            justify="center", 
            fg="gray"
        ).pack(expand=True)
        
        Label(
            self.metadata_content, 
            text="No components found", 
            justify="center", 
            fg="gray"
        ).pack(expand=True)
        
        Label(
            self.image_content, 
            text="No components found", 
            justify="center", 
            fg="gray"
        ).pack(expand=True)

        # Clear button frame
        if hasattr(self, 'action_button_frame') and self.action_button_frame:
            self.action_button_frame.destroy()
            self.action_button_frame = None

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

        component_type_var = StringVar()
        component_type_var.set("Other")  # Default value

        component_types = [
            "Cable", "Capacitor", "Connector", "Crystal", "Diode", "Evaluation", "Hardware", "IC", "Inductor",
            "Kit", "LED", "Module", "Other", "Relay", "Resistor", "Sensor", "Switch", "Transformer", "Transistor"
        ]

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

        # details frame
        self.details_frame = Frame(self.current_frame, bd=2, relief="groove", padx=10, pady=20)
        self.details_frame.grid(row=0, column=4, columnspan=2, rowspan=6, sticky="nsew", padx=10)
        self.details_label = Label(self.details_frame, text="Component Details will appear here", justify="left")
        self.details_label.pack(fill="both", expand=True)

        self.details_frame.grid_rowconfigure(0, weight=1)      # Content row expands
        self.details_frame.grid_rowconfigure(1, weight=0)      # Button row stays fixed
        self.details_frame.grid_columnconfigure(0, weight=1)   # Part info column
        self.details_frame.grid_columnconfigure(1, weight=1)   # Metadata column  
        self.details_frame.grid_columnconfigure(2, weight=1)   # Image column


        def add_component():
            component_data = {key: entry_widget.get().strip() for key, (_, entry_widget) in fields.items()}

            if not component_data["part_number"]:
                messagebox.showerror("Error", "Part Number is required!")
                return None
            try:
                component_data["count"] = int(component_data["count"])
            except ValueError:
                messagebox.showerror("Error", "Count must be an integer!")
                return None
            try:
                component_data["low_stock"] = int(component_data["low_stock"])
            except ValueError:
                messagebox.showerror("Error", "Low Stock Threshold must be a number!")
                return None
            
            if not self.backend.check_duplicate(component_data): 
                self.ledControl.turn_off_recent()
                update_add_tree()
                for key, (_, widget) in fields.items():
                    if isinstance(widget, Entry):
                        widget.delete(0, END)
                    else:
                        component_type_var.set("Other")
                return None
            
            fetch_digikey_data(self)
        
        def fetch_digikey_data(self, part=None):
            if part:
                response = self.digikeyAPI.fetch_part_details(part["part_number"])
                response["part_info"]["count"] = part["count"]
                response["metadata"]["low_stock"] = part["low_stock"]
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
                                "product_url": "N/A",
                                "in_use": "Available"
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
                        return None
                else: #found digikey component
                    if response.get("metadata", {}).get("photo_url") == "N/A":
                        messagebox.showerror("No Image", "No image URL to load.")
                    else:
                        image_entry = self.digikeyAPI.fetch_image_data(
                            photo_url=response.get("metadata", {}).get("photo_url"),
                            part_number=response.get("part_info", {}).get("part_number")
                        )
                        self.imageCache.store_entry(image_entry)
                    if part is None:
                        response["part_info"]["count"] = component_data["count"]
                        response["metadata"]["low_stock"] = component_data["low_stock"]
                        response['part_info']['location'] = component_data['location']

                    #Create dic for duplicate checking
                    component = {
                        "part_number":response["part_info"]["part_number"],
                        "count":response["part_info"]["count"]
                    }

                    if self.backend.check_duplicate(component) == False: 
                        self.ledControl.turn_off_recent()
                        update_add_tree()
                        
                        for key, (_, widget) in fields.items():
                            if isinstance(widget, Entry):
                                widget.delete(0, END)
                            else:
                                component_type_var.set("Other")

                        return None
            
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

            def process_barcode():
                """Detects barcode input and sends it to DigiKey API."""
                barcode = barcode_var.get().strip()

                try:
                    barcode_data=self.backend.barcode_decoder(barcode)
                except Exception as e:
                    return False

                if self.backend.check_duplicate(barcode_data)== False: 
                    self.ledControl.turn_off_recent()
                    update_add_tree()
                    
                    for key, (_, widget) in fields.items():
                        if isinstance(widget, Entry):
                            widget.delete(0, END)
                        else:
                            component_type_var.set("Other")

                    return True

                extraInfo = Toplevel(self.root)
                extraInfo.title("Barcode Info")
                extraInfo.geometry("300x150")
                extraInfo.resizable(False, False)

                low_stock_var = StringVar(extraInfo)
                Label(extraInfo, text="Low Stock Threshold:").pack(pady=5)
                Entry(extraInfo, textvariable=low_stock_var, width=20).pack(pady=5, padx=15)

                extraInfo.focus_set()

                def low_stock_entry_handeling(event):
                    low_stock = int(low_stock_var.get())
                    extraInfo.destroy()  # Close the window
                    if barcode:
                        barcode_data['low_stock'] = low_stock

                        fetch_digikey_data(self, barcode_data)
                
                Button(extraInfo, text="Save", command= low_stock_entry_handeling).pack(pady= 5)
                extraInfo.bind("<Return>", low_stock_entry_handeling)
                return True

            def on_enter(event):
                if process_barcode():
                    barcode_window.destroy()
                    return
                else:
                    barcode_window.focus_set()

            # Bind the Enter key to process barcode input
            barcode_entry.bind("<Return>", on_enter)

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
                    Label(header_frame, text="Low-Stock Threshold", width=20, anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=5)

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
                if self.backend.check_duplicate(barcode_data) == False: 
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
        Button(self.current_frame, text="Add Barcode", command=barcode_scan).grid(row=len(fields), column=2, columnspan=2, padx=10, pady=5, sticky= "w")
        Button(self.current_frame, text="Bulk Scan", command=lambda: bulk_add(self)).grid(row=len(fields), column=3, columnspan=2, padx=10, pady=5, sticky= "w")

        for _, (_, entry_widget) in fields.items(): entry_widget.bind("<Return>", lambda event: add_component())
        
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
        add_tree.bind("<<TreeviewSelect>>", lambda event: self.show_component_details(event))

        update_add_tree()

        # Edit button
        Button(self.current_frame, text="Edit Component", command=lambda: self.edit_component(add_tree)).grid(row=len(fields), column=1, columnspan=1, pady=10, sticky="w")

        # Bind delete key
        add_tree.bind("<Delete>", lambda event: self.delete_component(add_tree))
    
    def show_component_details(self, event):
        tree = event.widget
        selected = tree.selection()

        if not selected:
            for widget in self.details_frame.winfo_children():
                widget.destroy()
            Label(self.details_frame, text="No component selected", justify="left").pack(fill="both", expand=True)
            return None

        item = tree.item(selected[0], "values")
        part_number = item[0]

        # Look up component
        component = next((comp for comp in self.backend.get_all_components()
                        if comp["part_info"]["part_number"].strip().lower() == part_number.strip().lower()), None)
        if not component:
            return None

        # TURN OFF previously highlighted LED
        new_location = component["part_info"].get("location", "").strip()
        if self.last_highlighted_location and self.last_highlighted_location != new_location:
            self.ledControl.turn_off_led(self.last_highlighted_location)

        # Turn ON new LED
        self.ledControl.set_led_on(new_location, 0, 255, 0)
        self.last_highlighted_location = new_location

        # Clear any previous details
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        # Create three subframes: Part Info, Metadata, Image
        part_info_frame = Frame(self.details_frame, bd=1, relief="solid", padx=5, pady=5, width=250)
        part_info_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        meta_frame = Frame(self.details_frame, bd=1, relief="solid", padx=5, pady=5, width=250)
        meta_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        image_frame = Frame(self.details_frame, bd=1, relief="solid", padx=5, pady=5, width=250)
        image_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        for frame in [ part_info_frame, meta_frame, image_frame ]:
            frame.grid_rowconfigure(1, weight=1)
            frame.grid_columnconfigure(0, weight=1)

        #meta_frame.grid_propagate(False)
        #part_info_frame.grid_propagate(False)

        # Headers
        Label(
            part_info_frame, text="Part Info", font=("Arial", 12, "bold"), bg="lightgrey"
        ).grid( row=0, column=0, columnspan=2, pady=(0,5), sticky="ew")
        Label(
            meta_frame, text="Meta Data", font=("Arial", 12, "bold"), bg="lightgrey"
        ).grid( row=0, column=0, columnspan=2, pady=0 )
        Label(
            image_frame, text="Image", font=("Arial", 12, "bold"), bg="lightgrey"
        ).grid( row=0, column=0, columnspan=2, pady=0 )

        # scrollable content
        part_content = Frame(part_info_frame)
        part_content.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)

        meta_content = Frame(meta_frame)
        meta_content.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)

        # Populate Part Info (each key-value pair on its own row)
        # create new container per field for better auto-scaling
        """
        ┌─────────────────────────────────────┐
        │ part_content (parent container)     │
        │                                     │
        │ ┌─────────────────────────────────┐ │ ← field_frame for part_number
        │ │ Part Number:    │ 497-2944-5-ND │ │
        │ └─────────────────────────────────┘ │
        │                                     │
        │ ┌─────────────────────────────────┐ │ ← field_frame for manufacturer_number  
        │ │ Manufacturer:   │ L6234PD       │ │
        │ └─────────────────────────────────┘ │
        │                                     │
        │ ┌─────────────────────────────────┐ │ ← field_frame for location
        │ │ Location:       │ 1I            │ │
        │ └─────────────────────────────────┘ │
        │                                     │
        │ ... and so on for each field       │
        └─────────────────────────────────────┘
        """
        row_idx = 1 # header is row 0
        for key, value in component["part_info"].items():
            field_frame = Frame(part_content)
            field_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            field_frame.grid_columnconfigure(1, weight=1)
            # create the Label
            Label(
                    field_frame, text=f"{key.replace('_', ' ').title()}:", anchor="w", font=("Arial", 9, "bold")
            ).grid( row=0, column=0, sticky="nw", padx=(0,5))
            Label(
                    field_frame, text=f"{value}", anchor="w", wraplength=140, justify="left"
            ).grid( row=0, column=1, sticky="ew")
            row_idx += 1

        # Populate Meta Data similarly
        meta_fields = ["price", "low_stock", "description", "in_use" ]
        row_idx = 0
        for key in meta_fields:
            value = component.get("metadata", {}).get(key, "N/A")

            field_frame = Frame(meta_content)
            field_frame.grid(row=row_idx, column=0, sticky="ew", pady=1)
            field_frame.grid_columnconfigure(1, weight=1)

            Label(field_frame, text=f"{key.replace('_', ' ').title()}:", anchor="w", font=("Arial", 9, "bold")
            ).grid( row=0, column=0, sticky="nw", padx=(0,5) )
            
            # create text wrapping for description
            if key == "description":
                value_label = Label( field_frame, text=str(value), anchor="w", wraplength=120, justify="left" )
            else:
                value_label = Label( field_frame, text=str(value), anchor="w" )

            value_label.grid( row=0, column=1, sticky="ew" )
            row_idx += 1


        # Label(meta_frame, text=f"Price:", anchor="w").grid(row=1, column=1, sticky="w", padx=2, pady=2)
        # Label(meta_frame, text=component["metadata"]["price"], anchor="w").grid(row=1, column=1, sticky="w", padx=(100,2), pady=2)
        # Label(meta_frame, text=f"Low Stock:", anchor="w").grid(row=2, column=1, sticky="w", padx=2, pady=2)
        # Label(meta_frame, text=component["metadata"]["low_stock"], anchor="w").grid(row=2, column=1, sticky="w", padx=(100,2), pady=2)
        # Label(meta_frame, text=f"Description:", anchor="w").grid(row=3, column=1, sticky="w", padx=2, pady=2)
        # Label(meta_frame, text=component["metadata"]["description"], anchor="w").grid(row=3, column=1, sticky="w", padx=(100,2), pady=2)
        # Label(meta_frame, text=f"In Use?:", anchor="w").grid(row=4, column=1, sticky="w", padx=2, pady=2)
        # Label(meta_frame, text=component["metadata"]["in_use"], anchor="w").grid(row=4, column=1, sticky="w", padx=(100,2), pady=2)

        # Create image container
        image_container = Frame ( image_frame, width=200, height=200, bg="white" )
        image_container.grid( row=1, column=0, columnspan=2, padx=5, pady=5 )
        image_container.grid_propagate( False )
        image_container.grid_rowconfigure( 0, weight=1 )     # weight 1 so it centers
        image_container.grid_columnconfigure( 0, weight=1 )  # ^
        try:
            image_entry = self.digikeyAPI.fetch_image_data(
                photo_url=component.get("metadata", {}).get("photo_url", ""),
                part_number=component.get("part_info", {}).get("part_number", "")
            )
            if image_entry and image_entry.image:
                pil_image = Image.open( BytesIO( image_entry.image ) )
                pil_image.thumbnail( (180,180) ) # slightly smaller than the frame
                tk_image = ImageTk.PhotoImage( pil_image )

                image_label = Label( image_frame, image=tk_image )
                image_label.image = tk_image # no garbage collection
                image_label.grid( row=0, column=0 )
            else:
                  Label( 
                      image_container, text=f"No Image\nAvailable", justify="center", font=("Arial", 10)
                  ).grid( row=0, column=0 )
        except Exception as e:
                  Label( 
                      image_container, text=f"Image Error:\n{str(e)}...", justify="center", font=("Arial", 10), fg="red"
                  ).grid( row=0, column=0 )

        # create button panel
        button_frame = Frame( self.details_frame )
        button_frame.grid( row=1, column=0, columnspan=3, sticky="ew", padx=2, pady=5 )

        button_frame.grid_columnconfigure( 0, weight=1 )
        button_frame.grid_columnconfigure( 1, weight=1 )
        button_frame.grid_columnconfigure( 2, weight=1 )

        highlight_state = { "on": False }   # Track whether the LED is currently highlighted.

        highlight_color = ( 0, 255, 0 )

        def toggle_highlight():
            if not highlight_state["on"]:
                self.ledControl.set_led_on(component["part_info"]["location"], *highlight_color)
                highlight_button.config(text="Turn Off", relief='sunken')
                highlight_state["on"] = True
            else:
                self.ledControl.turn_off_led(component["part_info"]["location"])
                highlight_button.config(text="Highlight", relief='raised')
                highlight_state["on"] = False

        highlight_button = Button( 
            self.details_frame, 
            text="Highlight", 
            command=toggle_highlight 
        )
        highlight_button.grid( row=6, column=0, pady=2, padx=5, sticky="ew" )

        checkout_button = Button(
            self.details_frame, 
            text="Checkout", 
            command=lambda: self.checkout_component(tree)
        )
        checkout_button.grid( row=6, column=1, pady=2, padx=5, sticky="ew" )

        edit_button = Button( 
            self.details_frame, 
            text="Edit Component", 
            command=lambda: self.edit_component(tree)
        )
        edit_button.grid( row=6, column=2, pady=2, padx=5, sticky="ew" )

    def edit_component(self, tree):
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "No component selected!")
            return

        item = tree.item(selected_item[0], "values")
        part_number = item[0].strip().lower()

        # Find the actual component and its index in backend.components
        component = None
        index = -1
        for i, comp in enumerate(self.backend.get_all_components()):
            if comp["part_info"]["part_number"].strip().lower() == part_number:
                component = comp
                index = i
                break

        if component is None:
            messagebox.showerror("Error", "Component not found in backend.")
            return

        edit_window = Toplevel(self.root)
        edit_window.title("Component View")
        edit_window.geometry("620x515") # Adjust width to accommodate extra panel
        edit_window.resizable(width=False, height=False)
        edit_window.attributes('-topmost', True)

        highlight_state = {"on": False}  # Track whether the LED is currently highlighted.
        def on_close():
            if highlight_state["on"]:
                self.ledControl.turn_off_led(component["part_info"]["location"])
            edit_window.destroy()
        edit_window.protocol("WM_DELETE_WINDOW", on_close)

        # Left side: Part Info & Metadata fields
        fields = {}
        Label(edit_window, text="Part Information", font=("Arial", 12, "bold")).grid(row=0, column=1, columnspan=1, pady=5)

        for i, key in enumerate(["part_number", "manufacturer_number", "location", "count", "type"]):
            Label(edit_window, text=key.replace("_", " ").title() + ":").grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            entry = Entry(edit_window, width=30)
            entry.insert(0, str(component["part_info"][key]))
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
            fields[key] = entry

        Label(edit_window, text="Metadata", font=("Arial", 12, "bold")).grid(row=7, column=0, columnspan=2, pady=5)

        metadata_fields = {}
        for i, key in enumerate(["price", "low_stock", "description", "photo_url", "datasheet_url", "product_url", "in_use"]):
            Label(edit_window, text=key.replace("_", " ").title() + ":").grid(row=i+8, column=0, padx=10, pady=5, sticky="w")
            entry = Entry(edit_window, width=40)
            entry.insert(0, str(component["metadata"].get(key, "N/A")))
            entry.grid(row=i+8, column=1, padx=10, pady=5, sticky="ew")
            metadata_fields[key] = entry

        # Right side panel: Display part image and link buttons
        right_frame = Frame(edit_window, bd=2, relief="groove")
        right_frame.grid(row=12, column=2, columnspan=2, rowspan=2, padx=10, sticky="n")

        # Datasheet and Product Page buttons
        datasheet_url = component["metadata"].get("datasheet_url", "")
        product_url = component["metadata"].get("product_url", "")

        if datasheet_url and datasheet_url != "N/A":
            Button(right_frame, text="Datasheet", command=lambda: webbrowser.open(datasheet_url)).pack(pady=5, fill="x")
        if product_url and product_url != "N/A":
            Button(right_frame, text="Product Page", command=lambda: webbrowser.open(product_url)).pack(pady=5, fill="x")

        # Existing Highlight button and Save Changes functionality
        highlight_color = (0, 255, 0)
        def toggle_highlight():
            if not highlight_state["on"]:
                self.ledControl.set_led_on(component["part_info"]["location"], *highlight_color)
                highlight_button.config(text="Highlight", relief='sunken')
                highlight_state["on"] = True
            else:
                self.ledControl.turn_off_led(component["part_info"]["location"])
                highlight_button.config(text="Highlight", relief='raised')
                highlight_state["on"] = False

        highlight_button = Button(edit_window, text="Highlight", command=toggle_highlight)
        highlight_button.grid(row=6, column=0, columnspan=2, pady=10)

        def save_changes():
            updated_data = {"part_info": {}, "metadata": {}}
            for key, entry in fields.items():
                updated_data["part_info"][key] = entry.get().strip()
            try:
                updated_data["part_info"]["count"] = int(updated_data["part_info"]["count"])
            except ValueError:
                messagebox.showerror("Error", "Count must be an integer!")
                return

            new_metadata = {}
            metadata_changed = False
            for key, entry in metadata_fields.items():
                new_val = entry.get().strip()
                new_metadata[key] = new_val
                original_val = str(component["metadata"].get(key, "N/A"))
                if new_val != original_val:
                    metadata_changed = True
            if metadata_changed:
                if not askyesno("Confirm Metadata Change", "Metadata fields have been modified. Are you sure you want to save these changes?"):
                    return

            updated_data["metadata"] = new_metadata

            self.backend.edit_component(index, updated_data)
            messagebox.showinfo("Success", "Component updated successfully!")
            if highlight_state["on"]:
                self.ledControl.turn_off_led(component["part_info"]["location"])
            edit_window.destroy()
            tree.item(selected_item, values=(
                updated_data["part_info"]["part_number"],
                updated_data["part_info"]["manufacturer_number"],
                updated_data["part_info"]["location"],
                updated_data["part_info"]["count"],
                updated_data["part_info"]["type"]
            ))

        Button(edit_window, text="Save Changes", command=save_changes).grid(row=6, column=1, columnspan=2, pady=10)
        edit_window.bind("<Return>", lambda event: save_changes())

    def delete_component(self, tree):
        selected_item = tree.selection()
        if not selected_item:
            return

        item = tree.item(selected_item[0], "values")
        part_number = item[0].strip().lower()

        # Find index of component in backend
        index = -1
        for i, comp in enumerate(self.backend.get_all_components()):
            if comp["part_info"]["part_number"].strip().lower() == part_number:
                index = i
                break

        if index == -1:
            messagebox.showerror("Error", "Component not found in backend.")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete part: {part_number}?")
        if confirm:
            self.backend.delete_component(index)
            self.backend.save_components()
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

    def process_bom_file(self, mode):
        file_path = askopenfilename(
            title="Select BOM File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            messagebox.showerror("Error", "No file selected!")
            return

        try:
            bom_list = self.backend.parse_bom(file_path)
        except Exception as e:
            messagebox.showerror("Error reading BOM", str(e))
            return

        if mode == "out":
            self.bom_out_preview(bom_list, board_name=os.path.basename(file_path))
        else:
            self.bom_in_preview(bom_list)

    def bom_out_preview(self, bom_list, board_name):
        preview_win = Toplevel(self.root)
        preview_win.title("BOM Preview")
        preview_win.geometry("700x400")
        preview_win.grab_set()

        # ——— Treeview with Location column ———
        cols = ("Digikey", "Quantity", "Found", "Current Count", "Location")
        tree = Treeview(preview_win, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor="center")
        tree.column("Digikey", width=150, anchor="w")

        tree.tag_configure('missing', background='tomato')
        tree.tag_configure('out_of_stock', background='yellow')

        # insert rows, now including location
        for row in bom_list:
            try:
                qty = int(row.get("quantity", 0))
            except ValueError:
                qty = 0
            current = row.get("current_count", 0) or 0

            if not row.get("found"):
                tags = ('missing',)
            elif current < qty:
                tags = ('out_of_stock',)
            else:
                tags = ()
            tree.insert("", "end",
                        values=(
                            row["digikey"],
                            row["quantity"],
                            "Yes" if row.get("found") else "No",
                            row.get("current_count", "N/A"),
                            row.get("location", "N/A")
                        ),
                        tags=tags)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        # helper to get location safely
        def get_selected_location():
            sel = tree.selection()
            if not sel:
                return None
            vals = tree.item(sel[0], "values")
            # now vals[4] always exists
            return vals[4]

        # highlight a single vial with odd/even color from LedController
        def on_select(event=None):
            loc = get_selected_location()
            if loc:
                self.ledControl.highlight_location(loc)

        # bind both mouse and keyboard navigation
        tree.bind("<<TreeviewSelect>>", on_select)
        tree.bind("<ButtonRelease-1>", on_select)
        tree.bind("<Up>", on_select)
        tree.bind("<Down>", on_select)

        # ——— Consume button ———
        def process_bom_callback():
            results = self.backend.process_bom_out(bom_list, board_name)
            preview_win.destroy()

            # light all remaining locations
            locs = [row["location"] for row in bom_list
                    if row.get("found") and row.get("location")]
            self.ledControl.highlight_all(locs)

            grab_win = Toplevel(self.root)
            grab_win.title("Grab Components")
            grab_win.geometry("300x150")
            Label(grab_win,
                  text="Please grab all vials highlighted in color.\nPress Enter or click OK when done.",
                  justify="center").pack(pady=20)
            
            def finish():
                # completely clear every LED
                self.ledControl.turn_off_all()
                grab_win.destroy()
                self.show_bom_results(results)

            Button(grab_win, text="OK", width=10, command=finish).pack(pady=10)
            grab_win.bind("<Return>", lambda e: finish())
            grab_win.protocol("WM_DELETE_WINDOW", finish)

        Button(preview_win, text="Consume Components?", command=process_bom_callback).pack(pady=10)
        preview_win.protocol("WM_DELETE_WINDOW", lambda: (self.ledControl.turn_off_all(), preview_win.destroy()))

    def bom_in_preview(self, bom_list):
            preview_win = Toplevel(self.root)
            preview_win.title("BOM Preview")
            preview_win.geometry("600x400")
            preview_win.grab_set()

            preview_win.protocol("WM_DELETE_WINDOW", lambda: (self.ledControl.turn_off_bom_leds(bom_list, self.ledControl), preview_win.destroy()))

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

            def process_bom_callback(parent_win, bom_list):
                """
                Loops through each BOM row to collect additional usage and handles LED blinking,
                then calls the backend to process the returned vials.
                """
                # Close the return window to avoid interference with dialogs.
                parent_win.destroy()
                
                # Dictionary to store additional usage keyed by a unique component identifier (e.g., digikey).
                additional_usage = {}
                
                for row in bom_list:
                    location = row.get("location")
                    digikey = row.get("digikey", "N/A")
                    if not location:
                        continue  # Skip if no location
                    
                    # Ask the user for additional components used (allowing blank input)
                    additional_str = simpledialog.askstring(
                        "Additional Components",
                        f"For component {digikey} at location {location} \nEnter additional components used (or leave blank):", parent=self.root
                    )
                    try:
                        additional = int(additional_str) if additional_str and additional_str.strip() != "" else 0
                    except ValueError:
                        additional = 0
                    additional_usage[digikey] = additional  # Save in the dictionary
                    
                    # Start blinking the LED at this location.
                    # (You might implement actual blinking by toggling the LED on and off; here we simply set it on.)
                    self.ledControl.set_led_on(location, 0, 255, 0)
                    
                    # Show a message instructing the user to return the component.
                    message = f"Return component {digikey} to {location}.\nPress OK when returned."
                    messagebox.showinfo("Return Component", message, parent=self.root)
                    
                    # Stop blinking the LED.
                    self.ledControl.turn_off_led(location)
                
                # Now pass the collected data to the backend for processing.
                results = self.backend.process_returned_vials(bom_list, additional_usage)
                
                self.show_bom_results(results)

            Button(preview_win, text="Return Components?", command=lambda: process_bom_callback(preview_win, bom_list)).pack(pady=10)
                            
    def show_bom_results(self, results):
        result_win = Toplevel(self.root)
        result_win.title("BOM Processing Results")
        result_win.geometry("600x400")
        result_win.lift()
        
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
        selected = tree.selection()
        if not selected:
            messagebox.showerror("Error", "No component selected!")
            return

        part_number = tree.item(selected[0], "values")[0]

        # Prompt for quantity
        checkout_win = Toplevel(self.root)
        checkout_win.title("Checkout Part")
        checkout_win.geometry("300x150")
        Label(checkout_win, text="How many components to remove?").pack(pady=10)
        qty_entry = Entry(checkout_win)
        qty_entry.pack(pady=5)
        qty_entry.focus_set()

        def submit_qty(event=None):
            try:
                qty = int(qty_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid integer")
                return

            checkout_win.destroy()
            result = self.backend.checkout(part_number, qty)
            if not result["success"]:
                messagebox.showerror("Checkout Failed", result["message"])
                return

            loc = result["location"]
            # Light the LED
            self.ledControl.set_led_on(loc, 0, 255, 0)

            # Inform user and wait for replacement
            lit_win = Toplevel(self.root)
            lit_win.title("Component Lit Up")
            lit_win.geometry("300x150")
            Label(lit_win, text=result["message"]).pack(pady=20)
            Label(lit_win, text="Press Enter or click OK when replaced.").pack(pady=10)
            lit_win.focus_set()

            def confirm_replaced(event=None):
                lit_win.destroy()
                if messagebox.askyesno("Confirm Replacement", "Have you replaced the vial?"):
                    self.ledControl.turn_off_led(loc)
                    messagebox.showinfo("Success", result["message"])
                    # Refresh the treeview
                    for item in tree.get_children():
                        tree.delete(item)
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

        checkout_win.bind("<Return>", submit_qty)
        Button(checkout_win, text="Submit", command=submit_qty).pack(pady=10)

    def undo_last_deletion(self):
        if self.backend.undo_delete():
            messagebox.showinfo("Undo", "Last deletion undone!")
        else:
            messagebox.showinfo("Undo", "No deletion to undo.")

    def refresh_treeview(self, tree):
        """
        Clears and repopulates the given Treeview widget with the latest components.
        Expects the Treeview to have columns in the following order:
        Part Number, Manufacturer Number, Location, Count, Type.
        """
        # Clear all existing items.
        for item in tree.get_children():
            tree.delete(item)
            
        # Repopulate the tree with the current components.
        for comp in self.backend.get_all_components():
            tree.insert("", "end", values=(
                comp["part_info"].get("part_number", "N/A"),
                comp["part_info"].get("manufacturer_number", "N/A"),
                comp["part_info"].get("location", "N/A"),
                comp["part_info"].get("count", "N/A"),
                comp["part_info"].get("type", "N/A")
            ))
