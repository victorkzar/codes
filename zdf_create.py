#@ Autor VICTOR COSTA PACHECO  bbyaga
import tkinter as tk # para interface template
from tkinter import ttk, filedialog, messagebox
import rasterio
from rasterio.plot import show
from pyproj import Transformer, Geod
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Converter para DECIMO MINUTOS E SEGUNDOS
def decimal_to_dms(value, is_lat):
    degrees = int(abs(value))
    minutes_float = (abs(value) - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    compass = 'N' if is_lat and value >= 0 else 'S' if is_lat else 'E' if value >= 0 else 'W'
    return f"{degrees}°{minutes:02d}'{seconds:04.1f}\"{compass}"

class LineDrawer: # desenhar as linhas  na figura do plot
    def __init__(self, ax, crs, num_lines, length_nm):
        self.ax = ax
        self.fig = ax.figure
        self.crs = crs
        self.num_lines = num_lines # input no template do tkinter
        self.length_nm = length_nm
        self.clicks = []
        self.lines = []
        self.zones = []
        self.transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)#melhora a projeção d area
        self.inverse_transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self.geod = Geod(ellps='WGS84')

        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)

    def on_click(self, event): # função de click para inputar as estaçoes
        if event.inaxes != self.ax:
            return
        self.clicks.append((event.xdata, event.ydata))
        if len(self.clicks) == 2:
            x0, y0 = self.clicks[0]
            x1, y1 = self.clicks[1]

            self.ax.plot([x0, x1], [y0, y1], color='red', linewidth=2)
            lon0, lat0 = self.transformer.transform(x0, y0)
            lon1, lat1 = self.transformer.transform(x1, y1)

            print("\nLinha Principal:")
            print(f"Estação 1: {decimal_to_dms(lat0, True)}, {decimal_to_dms(lon0, False)}")
            print(f"Estação 2: {decimal_to_dms(lat1, True)}, {decimal_to_dms(lon1, False)}\n")

            self.draw_perpendiculars(lat0, lon0, lat1, lon1)
            self.clicks = []
            self.fig.canvas.draw()
            self.plot_zones()
            self.export_zdf()

    def on_key_press(self, event):
        if event.key == 'ctrl+z' and self.lines:
            last_line = self.lines.pop()
            last_line.remove()
            self.fig.canvas.draw()
            print("Última linha removida.")

    def draw_perpendiculars(self, lat0, lon0, lat1, lon1):
        az12, az21, dist = self.geod.inv(lon0, lat0, lon1, lat1)
        perpendiculars = []

        for i in range(self.num_lines + 1):
            frac = i / self.num_lines
            lon_mid, lat_mid, _ = self.geod.fwd(lon0, lat0, az12, dist * frac)
            perp_az = az12 + 90
            length_m = self.length_nm * 1852

            lon_a, lat_a, _ = self.geod.fwd(lon_mid, lat_mid, perp_az, length_m / 2)
            lon_b, lat_b, _ = self.geod.fwd(lon_mid, lat_mid, perp_az + 180, length_m / 2)

            x_a, y_a = self.inverse_transformer.transform(lon_a, lat_a)
            x_b, y_b = self.inverse_transformer.transform(lon_b, lat_b)

            line, = self.ax.plot([x_a, x_b], [y_a, y_b], color='cyan', linestyle='--')
            self.lines.append(line)
            perpendiculars.append(((lon_a, lat_a), (lon_b, lat_b)))

        for i in range(len(perpendiculars) - 1):
            a1, a2 = perpendiculars[i]
            b1, b2 = perpendiculars[i + 1]
            poly = [a1, a2, b2, b1, a1]
            self.zones.append(poly)

    def plot_zones(self):
        fig2, ax2 = plt.subplots(figsize=(12, 10))
        ax2.set_title("Zonas de Maré")
        for idx, zone in enumerate(self.zones):
            lons, lats = zip(*zone)
            ax2.plot(lons, lats, marker='o')
            ax2.text(sum(lons)/len(lons), sum(lats)/len(lats), f'zone{idx+1:03d}', fontsize=9, ha='center')
        ax2.set_xlabel("Longitude")
        ax2.set_ylabel("Latitude")
        plt.grid(True)
        plt.show()

    def exportar_zdf(self, filename='zonas.zdf'):
        with open(filename, 'w') as f:
            f.write("[ZONE_DEF_VERSION_2]\n\n")

            for i, zone in enumerate(self.zones, start=1):
                f.write(f"[ZONE]\nA{i},5\n")
                for lon, lat in zone:
                    f.write(f"{lat:.8f},{lon:.8f}\n")
                f.write("\n")

            f.write("[TIDE_ZONE]\n\n[TIDE_STATION]\n\n[TIDE_AVERAGE]\n")
            for i in range(len(self.zones)):
                f.write(f"A{i + 1},\n")

        print(f"Arquivo '{filename}' exportado com sucesso!")

# Interface gráfica com tkinter
class App:
    def __init__(self, root):
        self.root = root
        root.title("Gerador de tide zone")
        self.kap_path = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        self.frame_1 = ttk.Frame(self.notebook)
        self.frame_2 = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_1, text="Selecionar Arquivo")
        self.notebook.add(self.frame_2, text="Inserir Coordenadas")

        self.build_frame_1()
        self.build_frame_2()

    def build_frame_1(self):
        ttk.Button(self.frame_1, text="Selecionar .KAP", command=self.select_file).pack(pady=10)

        self.num_lines_var = tk.IntVar(value=5)
        self.length_nm_var = tk.DoubleVar(value=1.0)

        ttk.Label(self.frame_1, text="Nº de Linhas Perpendiculares:").pack()
        ttk.Entry(self.frame_1, textvariable=self.num_lines_var).pack()

        ttk.Label(self.frame_1, text="Comprimento (milhas náuticas):").pack()
        ttk.Entry(self.frame_1, textvariable=self.length_nm_var).pack()

    def build_frame_2(self):
        self.lat0_var = tk.DoubleVar()
        self.lon0_var = tk.DoubleVar()
        self.lat1_var = tk.DoubleVar()
        self.lon1_var = tk.DoubleVar()

        ttk.Label(self.frame_2, text="Latitude Ponto 1:").pack()
        ttk.Entry(self.frame_2, textvariable=self.lat0_var).pack()

        ttk.Label(self.frame_2, text="Longitude Ponto 1:").pack()
        ttk.Entry(self.frame_2, textvariable=self.lon0_var).pack()

        ttk.Label(self.frame_2, text="Latitude Ponto 2:").pack()
        ttk.Entry(self.frame_2, textvariable=self.lat1_var).pack()

        ttk.Label(self.frame_2, text="Longitude Ponto 2:").pack()
        ttk.Entry(self.frame_2, textvariable=self.lon1_var).pack()

        ttk.Button(self.frame_2, text="Desenhar Manualmente", command=self.draw_from_input).pack(pady=10)

    def select_file(self):
        self.kap_path = filedialog.askopenfilename(filetypes=[("KAP files", "*.kap"), ("Todos os arquivos", "*.*")])
        if self.kap_path:
            self.plot_kap()

    def plot_kap(self):
        with rasterio.open(self.kap_path) as src:
            fig, ax = plt.subplots(figsize=(16, 14))

            if src.count == 1 and src.colorinterp[0].name == 'palette':
                band = src.read(1)
                palette = src.colormap(1)
                lut = np.zeros((256, 3), dtype='float32')
                for idx, rgba in palette.items():
                    r, g, b = rgba[:3]
                    lut[idx] = [r / 255, g / 255, b / 255]
                rgb_image = lut[band]
                extent = rasterio.plot.plotting_extent(src)
                ax.imshow(rgb_image, origin='upper', extent=extent)
            elif src.count >= 3:
                img = src.read([1, 2, 3]).transpose(1, 2, 0).astype('float32')
                img = (img - img.min()) / (img.max() - img.min())
                extent = rasterio.plot.plotting_extent(src)
                ax.imshow(img, origin='upper', extent=extent)
            else:
                show(src, ax=ax)

            ax.set_title("Carta Náutica — Clique 2x para linha / Ctrl+Z para desfazer")
            transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: decimal_to_dms(transformer.transform(x, 0)[0], False)))
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: decimal_to_dms(transformer.transform(0, y)[1], True)))
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            drawer = LineDrawer(ax, src.crs, self.num_lines_var.get(), self.length_nm_var.get())
            plt.tight_layout()
            plt.show()

    def draw_from_input(self):
        if not self.kap_path:
            messagebox.showerror("Erro", "Selecione um arquivo .KAP primeiro.")
            return
        with rasterio.open(self.kap_path) as src:
            fig, ax = plt.subplots(figsize=(16, 14))
            extent = rasterio.plot.plotting_extent(src)
            show(src, ax=ax)

            ax.set_title("Carta Náutica — Linha inserida manualmente")
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            x0, y0 = transformer.transform(self.lon0_var.get(), self.lat0_var.get())
            x1, y1 = transformer.transform(self.lon1_var.get(), self.lat1_var.get())
            ax.plot([x0, x1], [y0, y1], color='red', linewidth=2)

            drawer = LineDrawer(ax, src.crs, self.num_lines_var.get(), self.length_nm_var.get())
            drawer.draw_perpendiculars(self.lat0_var.get(), self.lon0_var.get(), self.lat1_var.get(), self.lon1_var.get())
            drawer.plot_zones()
            drawer.export_zdf()
            plt.tight_layout()
            plt.show()

# Execução da interface
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
