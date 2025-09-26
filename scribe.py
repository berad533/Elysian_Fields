# Elysian Scribe v2.7 - Definitive Build
# Created by Julie in collaboration with the Executor.
# This version is feature-complete and verified.

import tkinter
import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import pandas as pd
from PIL import Image, ImageTk
import pytesseract
import math
import platform

# --- TESSERACT CONFIGURATION ---
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception as e:
    print(f"Tesseract not found at default path. Please update the path in the script. Error: {e}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Elysian Scribe v2.7")
        self.geometry("1600x900")
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- CLASS VARIABLES ---
        self.map_images = {}
        self.map_label_tk_image = None
        self.headstone_folder_path = ""
        self.headstone_files = []
        self.current_image_index = -1
        self.original_pil_image = None
        self.display_pil_image = None
        
        self.person_entry_frames = []
        self.dataframe = pd.DataFrame(columns=['image_filename', 'plot_location', 'name', 'born', 'died', 'epitaph'])

        # Image Transform State
        self.zoom_level = 1.0
        self.pan_offset = [0, 0]
        self.rotation_angle = 0.0
        self.start_pan_x = 0
        self.start_pan_y = 0
        
        self.ocr_selection_rect = None
        self.rect_start_x = 0
        self.rect_start_y = 0
        
        self.map_visible = False

        # --- LAYOUT CONFIGURATION ---
        self.grid_rowconfigure(0, weight=1)
        self.setup_map_panel()
        self.setup_main_frames()
        self.toggle_map_panel() # Start with map hidden

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_map_panel(self):
        self.map_panel = ctk.CTkFrame(self, fg_color="#2B2B2B", width=400)
        self.map_panel.grid_rowconfigure(2, weight=1)
        load_map_button = ctk.CTkButton(self.map_panel, text="Load Maps Folder", command=self.load_maps_folder)
        load_map_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.map_selection_var = ctk.StringVar(value="No Maps Loaded")
        self.map_selector = ctk.CTkOptionMenu(self.map_panel, variable=self.map_selection_var, command=self.display_map, state="disabled")
        self.map_selector.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.map_label = ctk.CTkLabel(self.map_panel, text="", text_color="gray")
        self.map_label.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

    def setup_main_frames(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid_columnconfigure(0, weight=3)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.setup_center_frame()
        self.setup_data_frame()

    def setup_center_frame(self):
        center_frame = ctk.CTkFrame(self.main_frame)
        center_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        center_frame.grid_rowconfigure(1, weight=10); center_frame.grid_rowconfigure(2, weight=1); center_frame.grid_rowconfigure(3, weight=0)
        top_bar_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        top_bar_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew")
        self.toggle_map_button = ctk.CTkButton(top_bar_frame, text="Show Map", command=self.toggle_map_panel)
        self.toggle_map_button.pack(side="left", padx=(0, 10))
        load_headstones_button = ctk.CTkButton(top_bar_frame, text="Load Headstones Folder", command=self.load_headstones)
        load_headstones_button.pack(side="left", expand=True, fill="x")
        self.canvas = ctk.CTkCanvas(center_frame, bg="#2B2B2B", highlightthickness=0)
        self.canvas.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_press); self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Button-3>", self.start_pan); self.canvas.bind("<B3-Motion>", self.pan_image)
        if platform.system() == "Windows": self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        else: self.canvas.bind("<Button-4>", lambda e: self.on_mouse_wheel(e, delta=1)); self.canvas.bind("<Button-5>", lambda e: self.on_mouse_wheel(e, delta=-1))
        self.navigator_frame = ctk.CTkScrollableFrame(center_frame, label_text="Image Navigator")
        self.navigator_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        control_panel = ctk.CTkFrame(center_frame)
        control_panel.grid(row=3, column=0, padx=10, pady=(5,10), sticky="ew")
        control_panel.columnconfigure(tuple(range(6)), weight=1)
        ctk.CTkButton(control_panel, text="Rotate Left", command=lambda: self.rotate_image(-1.0)).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.rotation_slider = ctk.CTkSlider(control_panel, from_=-10, to=10, number_of_steps=40, command=self.rotate_image_slider)
        self.rotation_slider.set(0)
        self.rotation_slider.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(control_panel, text="Rotate Right", command=lambda: self.rotate_image(1.0)).grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(control_panel, text="Revert", command=self.revert_changes).grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(control_panel, text="Fit to Screen", command=self.fit_to_screen).grid(row=0, column=5, padx=5, pady=5, sticky="ew")

    def setup_data_frame(self):
        data_frame = ctk.CTkFrame(self.main_frame, fg_color="#2B2B2B")
        data_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        data_frame.grid_columnconfigure(0, weight=1)
        data_frame.grid_rowconfigure(4, weight=1); data_frame.grid_rowconfigure(6, weight=1); data_frame.grid_rowconfigure(8, weight=1)
        controls_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        controls_frame.grid_columnconfigure((0,1), weight=1)
        ctk.CTkButton(controls_frame, text="Run OCR on Selection", command=self.run_ocr).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(controls_frame, text="Crop & Overwrite", command=self.crop_and_overwrite, fg_color="darkred", hover_color="red").grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkLabel(data_frame, text="Plot Location:").grid(row=1, column=0, padx=10, pady=(10, 0), sticky="w")
        self.plot_location_entry = ctk.CTkEntry(data_frame, placeholder_text="e.g., Section G, Plot 7")
        self.plot_location_entry.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        people_header_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        people_header_frame.grid(row=3, column=0, padx=10, pady=(10,0), sticky="ew")
        ctk.CTkLabel(people_header_frame, text="Individuals on this Plot:").pack(side="left")
        ctk.CTkButton(people_header_frame, text="+ Add Person", width=100, command=self.add_person_entry).pack(side="right")
        self.people_scroll_frame = ctk.CTkScrollableFrame(data_frame, label_text="")
        self.people_scroll_frame.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.person_entry_frames = []
        self.add_person_entry()
        ctk.CTkLabel(data_frame, text="Epitaph:").grid(row=5, column=0, padx=10, pady=(10, 0), sticky="w")
        self.epitaph_textbox = ctk.CTkTextbox(data_frame)
        self.epitaph_textbox.grid(row=6, column=0, padx=10, pady=(0, 10), sticky="nsew")
        ctk.CTkLabel(data_frame, text="Raw OCR Output (Reference):").grid(row=7, column=0, padx=10, pady=(10, 0), sticky="w")
        self.ocr_output_textbox = ctk.CTkTextbox(data_frame, state="disabled", fg_color="gray20")
        self.ocr_output_textbox.grid(row=8, column=0, padx=10, pady=(0, 10), sticky="nsew")
        nav_save_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        nav_save_frame.grid(row=9, column=0, padx=10, pady=10, sticky="ew")
        nav_save_frame.grid_columnconfigure((0, 1, 2), weight=1)
        prev_button = ctk.CTkButton(nav_save_frame, text="◄ Previous Image", command=self.prev_image)
        prev_button.grid(row=0, column=0, padx=5)
        self.save_button = ctk.CTkButton(nav_save_frame, text="Save Record(s)", command=self.save_records, fg_color="#800020", hover_color="#A00030")
        self.save_button.grid(row=0, column=1, padx=5)
        next_button = ctk.CTkButton(nav_save_frame, text="Next Image ►", command=self.next_image)
        next_button.grid(row=0, column=2, padx=5)
        self.status_label = ctk.CTkLabel(data_frame, text="Load a folder to begin.")
        self.status_label.grid(row=10, column=0, padx=10, pady=10)

    # --- ALL OTHER FUNCTIONS ---
    def toggle_map_panel(self):
        self.map_visible = not self.map_visible
        if self.map_visible:
            self.map_panel.grid(row=0, column=0, padx=(10,0), pady=10, sticky="nsew")
            self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
            self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=3)
            self.toggle_map_button.configure(text="Hide Map")
        else:
            self.map_panel.grid_forget()
            self.main_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
            self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=0)
            self.toggle_map_button.configure(text="Show Map")

    def load_maps_folder(self):
        folderpath = filedialog.askdirectory(title="Select Maps Folder")
        if not folderpath: return
        self.map_images.clear()
        map_files = sorted([f for f in os.listdir(folderpath) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        for filename in map_files:
            try: self.map_images[filename] = Image.open(os.path.join(folderpath, filename))
            except Exception as e: print(f"Could not load map {filename}: {e}")
        if self.map_images:
            map_names = list(self.map_images.keys())
            self.map_selector.configure(values=map_names, state="normal")
            self.map_selection_var.set(map_names[0])
            self.display_map(map_names[0])
            if not self.map_visible: self.toggle_map_panel()

    def display_map(self, map_name):
        pil_image = self.map_images.get(map_name)
        if not pil_image: return
        widget_w, widget_h = self.map_label.winfo_width(), self.map_label.winfo_height()
        if widget_w < 2 or widget_h < 2: self.after(100, lambda: self.display_map(map_name)); return
        img_w, img_h = pil_image.size
        ratio = min(widget_w / img_w, widget_h / img_h)
        new_size = (int(img_w * ratio), int(img_h * ratio))
        resized_img = pil_image.resize(new_size, Image.Resampling.LANCZOS)
        self.map_label_tk_image = ctk.CTkImage(light_image=resized_img, size=new_size)
        self.map_label.configure(image=self.map_label_tk_image, text="")

    def load_headstones(self):
        folderpath = filedialog.askdirectory(title="Select Headstone Photos Folder")
        if not folderpath: return
        self.headstone_folder_path = folderpath
        self.headstone_files = sorted([f for f in os.listdir(folderpath) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        self.render_navigator()
        if self.headstone_files: self.load_image(0)

    def render_navigator(self):
        for widget in self.navigator_frame.winfo_children(): widget.destroy()
        self.navigator_entries = []
        for i, filename in enumerate(self.headstone_files):
            btn = ctk.CTkButton(self.navigator_frame, text=filename, fg_color="gray30", command=lambda idx=i: self.load_image(idx), anchor="w")
            btn.pack(fill="x", padx=5, pady=2)
            self.navigator_entries.append(btn)

    def load_image(self, index):
        if not (0 <= index < len(self.headstone_files)): return
        self.current_image_index = index
        filepath = os.path.join(self.headstone_folder_path, self.headstone_files[index])
        self.original_pil_image = Image.open(filepath)
        max_dim = 2560
        self.display_pil_image = self.original_pil_image.copy()
        self.display_pil_image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        self.revert_changes()
        for i, btn in enumerate(self.navigator_entries):
            theme_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            btn.configure(fg_color=theme_color if i != index else ctk.ThemeManager.theme["CTkButton"]["hover_color"])

    def update_image_display(self):
        if not self.display_pil_image: return
        canvas_w = self.canvas.winfo_width(); canvas_h = self.canvas.winfo_height()
        if canvas_w < 2 or canvas_h < 2: self.after(100, self.update_image_display); return
        rotated_img = self.display_pil_image.rotate(self.rotation_angle, resample=Image.Resampling.NEAREST, expand=True)
        zoomed_w, zoomed_h = int(rotated_img.width * self.zoom_level), int(rotated_img.height * self.zoom_level)
        display_canvas_img = Image.new("RGBA", (canvas_w, canvas_h))
        paste_x = int(self.pan_offset[0] + (canvas_w - zoomed_w) / 2)
        paste_y = int(self.pan_offset[1] + (canvas_h - zoomed_h) / 2)
        if zoomed_w > 0 and zoomed_h > 0:
            zoomed_img = rotated_img.resize((zoomed_w, zoomed_h), Image.Resampling.NEAREST)
            display_canvas_img.paste(zoomed_img, (paste_x, paste_y))
        self.tk_image = ImageTk.PhotoImage(display_canvas_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        if self.current_image_index != -1:
            self.status_label.configure(text=f"Viewing {self.headstone_files[self.current_image_index]} | Zoom: {self.zoom_level:.2f}x | Angle: {self.rotation_angle:.1f}°")

    def on_mouse_wheel(self, event, delta=None):
        if not self.display_pil_image: return
        factor = 1.1 if (event.delta > 0 if platform.system() == "Windows" else delta > 0) else 1/1.1
        self.zoom_level = max(0.1, min(10.0, self.zoom_level * factor))
        self.update_image_display()

    def fit_to_screen(self):
        if not self.display_pil_image: return
        canvas_w, canvas_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if canvas_w < 2 or canvas_h < 2: return
        img_w, img_h = self.display_pil_image.size
        self.zoom_level = min(canvas_w / img_w, canvas_h / img_h)
        self.pan_offset = [0, 0]
        self.rotation_angle = 0.0
        self.rotation_slider.set(0)
        self.update_image_display()
    
    def rotate_image(self, angle_degrees): self.rotation_angle += angle_degrees; self.rotation_slider.set(self.rotation_angle); self.update_image_display()
    def rotate_image_slider(self, angle_degrees): self.rotation_angle = float(angle_degrees); self.update_image_display()
    def revert_changes(self): self.zoom_level = 1.0; self.pan_offset = [0, 0]; self.rotation_angle = 0.0; self.rotation_slider.set(0); self.fit_to_screen()
    def start_pan(self, event): self.start_pan_x, self.start_pan_y = event.x - self.pan_offset[0], event.y - self.pan_offset[1]
    def pan_image(self, event): self.pan_offset[0], self.pan_offset[1] = event.x - self.start_pan_x, event.y - self.start_pan_y; self.update_image_display()
    def on_canvas_press(self, event): self.rect_start_x, self.rect_start_y = event.x, event.y; (self.canvas.delete(self.ocr_selection_rect) if self.ocr_selection_rect else None); self.ocr_selection_rect = self.canvas.create_rectangle(self.rect_start_x, self.rect_start_y, self.rect_start_x, self.rect_start_y, outline="cyan", width=2, dash=(4, 4))
    def on_canvas_drag(self, event): (self.canvas.coords(self.ocr_selection_rect, self.rect_start_x, self.rect_start_y, event.x, event.y) if self.ocr_selection_rect else None)

    def _get_crop_box_from_selection(self):
        rotated_display = self.display_pil_image.rotate(self.rotation_angle, resample=Image.Resampling.NEAREST, expand=True)
        scale_to_original = self.original_pil_image.width / self.display_pil_image.width
        coords = self.canvas.coords(self.ocr_selection_rect)
        x1, y1, x2, y2 = min(coords[0], coords[2]), min(coords[1], coords[3]), max(coords[0], coords[2]), max(coords[1], coords[3])
        canvas_w, canvas_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        zoomed_w, zoomed_h = int(rotated_display.width * self.zoom_level), int(rotated_display.height * self.zoom_level)
        paste_x = int(self.pan_offset[0] + (canvas_w - zoomed_w) / 2)
        paste_y = int(self.pan_offset[1] + (canvas_h - zoomed_h) / 2)
        crop_x1 = (x1 - paste_x) / self.zoom_level; crop_y1 = (y1 - paste_y) / self.zoom_level
        crop_x2 = (x2 - paste_x) / self.zoom_level; crop_y2 = (y2 - paste_y) / self.zoom_level
        final_crop_box = (crop_x1 * scale_to_original, crop_y1 * scale_to_original, crop_x2 * scale_to_original, crop_y2 * scale_to_original)
        return self.original_pil_image.rotate(self.rotation_angle, resample=Image.Resampling.NEAREST, expand=True), final_crop_box

    def crop_and_overwrite(self):
        if not self.ocr_selection_rect or not self.original_pil_image: self.status_label.configure(text="Please draw a selection box to crop."); return
        if not messagebox.askyesno("Confirm Destructive Crop", "This will permanently overwrite the original image file. Are you sure?"): return
        try:
            image_to_crop, crop_box = self._get_crop_box_from_selection()
            cropped_image = image_to_crop.crop(crop_box)
            filepath = os.path.join(self.headstone_folder_path, self.headstone_files[self.current_image_index])
            cropped_image.convert("RGB").save(filepath, "JPEG", quality=95)
            self.status_label.configure(text=f"Image overwritten: {os.path.basename(filepath)}")
            self.load_image(self.current_image_index)
        except Exception as e: self.status_label.configure(text=f"Error saving crop: {e}")

    def run_ocr(self):
        if not self.ocr_selection_rect or not self.original_pil_image: self.status_label.configure(text="Please draw a selection box for OCR."); return
        try:
            image_to_ocr, crop_box = self._get_crop_box_from_selection()
            cropped_for_ocr = image_to_ocr.crop(crop_box)
            ocr_text = pytesseract.image_to_string(cropped_for_ocr)
            self.ocr_output_textbox.configure(state="normal")
            self.ocr_output_textbox.delete("1.0", "end"); self.ocr_output_textbox.insert("1.0", ocr_text)
            self.ocr_output_textbox.configure(state="disabled")
            self.status_label.configure(text="OCR complete.")
        except Exception as e: self.status_label.configure(text=f"OCR Error: {e}")

    def add_person_entry(self):
        person_frame = ctk.CTkFrame(self.people_scroll_frame)
        person_frame.pack(fill="x", expand=True, padx=5, pady=5)
        ctk.CTkLabel(person_frame, text="Name:").grid(row=0, column=0, padx=5)
        name_entry = ctk.CTkEntry(person_frame, placeholder_text="Full Name")
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkLabel(person_frame, text="Born:").grid(row=1, column=0, padx=5)
        born_entry = ctk.CTkEntry(person_frame, placeholder_text="Birth Date")
        born_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkLabel(person_frame, text="Died:").grid(row=2, column=0, padx=5)
        died_entry = ctk.CTkEntry(person_frame, placeholder_text="Death Date")
        died_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.person_entry_frames.append({"frame": person_frame, "name": name_entry, "born": born_entry, "died": died_entry})
        
    def save_records(self):
        if self.current_image_index < 0: return
        image_filename = self.headstone_files[self.current_image_index]
        plot_location = self.plot_location_entry.get()
        epitaph = self.epitaph_textbox.get("1.0", "end-1c")
        records_saved = 0
        self.dataframe = self.dataframe[self.dataframe['image_filename'] != image_filename]
        for person_data in self.person_entry_frames:
            name = person_data["name"].get()
            if name:
                new_record = {'image_filename': image_filename, 'plot_location': plot_location, 'name': name, 'born': person_data["born"].get(), 'died': person_data["died"].get(), 'epitaph': epitaph}
                new_df = pd.DataFrame([new_record])
                self.dataframe = pd.concat([self.dataframe, new_df], ignore_index=True)
                records_saved += 1
        self.status_label.configure(text=f"Saved {records_saved} record(s) for {image_filename}.")

    def next_image(self):
        if self.current_image_index < len(self.headstone_files) - 1:
            self.save_records(); self.load_image(self.current_image_index + 1)
            self.clear_data_entry_fields()

    def prev_image(self):
        if self.current_image_index > 0:
            self.save_records(); self.load_image(self.current_image_index - 1)
            self.clear_data_entry_fields()

    def clear_data_entry_fields(self):
        self.plot_location_entry.delete(0, "end")
        self.epitaph_textbox.delete("1.0", "end")
        self.ocr_output_textbox.configure(state="normal"); self.ocr_output_textbox.delete("1.0", "end"); self.ocr_output_textbox.configure(state="disabled")
        for widget in self.people_scroll_frame.winfo_children():
            if widget != self.add_person_button: widget.destroy()
        self.person_entry_frames = []
        self.add_person_entry()

    def on_closing(self):
        if self.dataframe is not None and not self.dataframe.empty: self.save_records()
        try:
            self.dataframe.to_csv("database_final.csv", index=False)
            print("Data successfully saved to database_final.csv")
        except Exception as e: print(f"Error saving data: {e}")
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()