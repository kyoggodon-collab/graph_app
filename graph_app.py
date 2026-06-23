import math
import re
import numpy as np
import pandas as pd

# ==========================================
# Matplotlibのバックエンドを明示的に固定 (起動の最適化)
# ==========================================
import matplotlib
matplotlib.use('TkAgg')  
import matplotlib.pyplot as plt

import tkinter as tk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import platform

# ==========================================
# 高DPI（ディスプレイスケーリング）対応 (Windows向け)
# ==========================================
if platform.system() == 'Windows':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ==========================================
# 1. フォント・初期設定
# ==========================================
plt.rcParams['font.family'] = 'Yu Mincho'  
plt.rcParams['axes.unicode_minus'] = False  
plt.rcParams['savefig.dpi'] = 200  
plt.rcParams['savefig.bbox'] = 'tight'  

FONT_GUI_TITLE = ("Yu Gothic", 14, "bold")
FONT_GUI_SUB = ("Yu Gothic", 11, "bold")
FONT_GUI_REG = ("Yu Gothic", 11)
FONT_GUI_SMALL = ("Yu Gothic", 10)

COLOR_CYCLE = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5', '#70AD47', '#264478', '#997300']

# ==========================================
# 2. 補助関数
# ==========================================
def get_nice_limits(vmin, vmax, num_ticks=6):
    if pd.isna(vmin) or pd.isna(vmax):
        return 0, 1
    if vmin == vmax: 
        return vmin - 1, vmax + 1
    margin = (vmax - vmin) * 0.01
    vmin -= margin
    vmax += margin

    n_intervals = num_ticks - 1
    raw_step = (vmax - vmin) / n_intervals
    mag = math.floor(math.log10(raw_step))
    mag_pow = 10 ** mag
    norm_step = raw_step / mag_pow

    if norm_step <= 1.0: nice_norm_step = 1.0
    elif norm_step <= 2.0: nice_norm_step = 2.0
    elif norm_step <= 2.5: nice_norm_step = 2.5
    elif norm_step <= 5.0: nice_norm_step = 5.0
    else: nice_norm_step = 10.0

    nice_step = nice_norm_step * mag_pow
    nice_min = math.floor(vmin / nice_step) * nice_step
    nice_max = nice_min + nice_step * n_intervals

    while nice_max < vmax:
        if nice_norm_step == 1.0: nice_norm_step = 2.0
        elif nice_norm_step == 2.0: nice_norm_step = 2.5
        elif nice_norm_step == 2.5: nice_norm_step = 5.0
        elif nice_norm_step == 5.0: nice_norm_step = 10.0
        else:
            nice_norm_step = 1.0
            mag_pow *= 10
        nice_step = nice_norm_step * mag_pow
        nice_min = math.floor(vmin / nice_step) * nice_step
        nice_max = nice_min + nice_step * n_intervals

    return nice_min, nice_max

def remove_unit(text):
    return re.sub(r'\s*[\[\(].*?[\]\)]', '', str(text)).strip()

def process_dataframe(df):
    if len(df.columns) < 2:
        return None, "データが1列しかありません。X軸と1つ以上のY軸が必要です。"

    original_names = [str(df.iloc[0, i]).strip() for i in range(len(df.columns))]
    df = df[1:].reset_index(drop=True)
    internal_cols = [f'col_{i}' for i in range(len(df.columns))]
    df.columns = internal_cols
    
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.dropna(how='all').reset_index(drop=True)
    if len(df) == 0:
        return None, "有効な数値データが2行目以降に見つかりませんでした。"

    final_names = []
    for i, name in enumerate(original_names):
        col_key = f'col_{i}'
        if i > 0 and '[V]' in name:
            valid_data = df[col_key].dropna()
            if not valid_data.empty and valid_data.abs().max() < 1.0:
                name = name.replace('[V]', '[mV]')
                df[col_key] = df[col_key] * 1000
        final_names.append(name)

    return df, final_names

# ==========================================
# 3. GUIアプリケーションクラス
# ==========================================
class GraphApp:
    def __init__(self, master):
        self.master = master
        self.master.title("多軸対応2Dグラフ描画ツール Developed by K.O.")
        self.master.geometry("1400x850")
        
        self.df = None
        self.axis_names = []
        self.entry_widgets = []
        self.base_dpi = 100  

        # --- イベントバインド ---
        self.master.bind("<Control-v>", lambda event: self.load_from_clipboard())
        self.master.bind("<Control-V>", lambda event: self.load_from_clipboard())
        
        # Ctrl + マウスホイールでのズーム操作 (Windows / Mac)
        self.master.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)
        # Linux環境向けのスクロール操作
        self.master.bind("<Control-Button-4>", self.on_mouse_wheel_zoom)
        self.master.bind("<Control-Button-5>", self.on_mouse_wheel_zoom)

        self.frame_main = tk.Frame(master)
        self.frame_main.pack(fill=tk.BOTH, expand=True)

        # グラフエリア（左側）
        self.frame_graph_container = tk.Frame(self.frame_main, bg="#D6D6D6")
        self.frame_graph_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.frame_toolbar = tk.Frame(self.frame_graph_container)
        self.frame_toolbar.pack(side=tk.TOP, fill=tk.X)

        self.graph_scroll_canvas = tk.Canvas(self.frame_graph_container, bg="#D6D6D6", highlightthickness=0)
        self.graph_hscrollbar = tk.Scrollbar(self.frame_graph_container, orient="horizontal", command=self.graph_scroll_canvas.xview)
        self.graph_vscrollbar = tk.Scrollbar(self.frame_graph_container, orient="vertical", command=self.graph_scroll_canvas.yview)
        
        self.graph_scroll_canvas.configure(xscrollcommand=self.graph_hscrollbar.set, yscrollcommand=self.graph_vscrollbar.set)
        self.graph_hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.graph_vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.graph_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.frame_canvas_interior = tk.Frame(self.graph_scroll_canvas, bg="#D6D6D6")
        self.interior_id = self.graph_scroll_canvas.create_window((0, 0), window=self.frame_canvas_interior, anchor="nw")

        self.fig = plt.Figure()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_canvas_interior)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(padx=30, pady=30)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_toolbar)
        self.toolbar.update()

        self.graph_scroll_canvas.bind("<Configure>", self.center_graph)
        self.frame_canvas_interior.bind("<Configure>", self.center_graph)

        # コントロールパネル（右側）
        self.frame_ctrl = tk.Frame(self.frame_main, width=340, padx=10, pady=10)
        self.frame_ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self.frame_ctrl, text="【操作パネル】", font=FONT_GUI_TITLE).pack(pady=(0, 5))

        self.btn_paste = tk.Button(self.frame_ctrl, text="📋 クリップボードから読込 (Ctrl+V)", 
                                   command=self.load_from_clipboard, bg="#4472C4", fg="white", font=FONT_GUI_SUB)
        self.btn_paste.pack(pady=5, fill=tk.X)

        self.btn_update = tk.Button(self.frame_ctrl, text="🔄 グラフ再描画・更新", 
                                    command=self.update_plot, bg="#70AD47", fg="white", font=FONT_GUI_SUB)
        self.btn_update.pack(pady=5, fill=tk.X)

        # ズーム機能スライダー
        tk.Frame(self.frame_ctrl, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=8)
        tk.Label(self.frame_ctrl, text="◆ グラフ表示ズーム (Ctrl+ホイール)", font=FONT_GUI_SUB).pack(anchor=tk.W)
        
        self.scale_zoom = tk.Scale(self.frame_ctrl, from_=30, to=300, resolution=10, orient=tk.HORIZONTAL, command=lambda e: self.apply_zoom())
        self.scale_zoom.set(100)  
        self.scale_zoom.pack(fill=tk.X, pady=(0, 5))

        # パラメータ個別制御スライダー
        tk.Frame(self.frame_ctrl, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=8)
        tk.Label(self.frame_ctrl, text="◆ グラフ領域（プロット枠）の個別制御", font=FONT_GUI_SUB).pack(anchor=tk.W)
        
        tk.Label(self.frame_ctrl, text="① プロット領域の純粋な横幅 (Plot Width):", font=FONT_GUI_SMALL, fg="#D2691E").pack(anchor=tk.W)
        self.scale_plot_w = tk.Scale(self.frame_ctrl, from_=2.0, to=10.0, resolution=0.1, orient=tk.HORIZONTAL, command=lambda e: self.update_plot())
        self.scale_plot_w.set(5.5)  
        self.scale_plot_w.pack(fill=tk.X, pady=(0, 5))

        tk.Label(self.frame_ctrl, text="② プロット領域の純粋な縦幅 (Plot Height):", font=FONT_GUI_SMALL, fg="#D2691E").pack(anchor=tk.W)
        self.scale_plot_h = tk.Scale(self.frame_ctrl, from_=1.5, to=8.0, resolution=0.1, orient=tk.HORIZONTAL, command=lambda e: self.update_plot())
        self.scale_plot_h.set(4.0)  
        self.scale_plot_h.pack(fill=tk.X, pady=(0, 5))

        tk.Label(self.frame_ctrl, text="③ 左側縦軸同士の間隔 (軸オフセット):", font=FONT_GUI_SMALL, fg="#FF4500").pack(anchor=tk.W)
        self.scale_offset = tk.Scale(self.frame_ctrl, from_=10, to=120, resolution=1, orient=tk.HORIZONTAL, command=lambda e: self.update_plot())
        self.scale_offset.set(50)  
        self.scale_offset.pack(fill=tk.X, pady=(0, 5))

        # 凡例設定
        tk.Frame(self.frame_ctrl, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=8)
        tk.Label(self.frame_ctrl, text="◆ レポート用・凡例表示設定", font=FONT_GUI_SUB).pack(anchor=tk.W)
        
        self.var_show_legend = tk.BooleanVar(value=True)
        self.chk_show_legend = tk.Checkbutton(
            self.frame_ctrl, text="凡例を表示する", 
            variable=self.var_show_legend, font=FONT_GUI_REG, command=self.update_plot
        )
        self.chk_show_legend.pack(anchor=tk.W, pady=(5, 0))

        self.var_transparent_legend = tk.BooleanVar(value=False) 
        self.chk_legend = tk.Checkbutton(
            self.frame_ctrl, text="凡例の背景を透過・枠線なしにする", 
            variable=self.var_transparent_legend, font=FONT_GUI_REG, command=self.update_plot  
        )
        self.chk_legend.pack(anchor=tk.W, pady=(0, 5))

        tk.Frame(self.frame_ctrl, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=8)
        tk.Label(self.frame_ctrl, text="◆ 凡例名のカスタム（空欄なら自動）", font=FONT_GUI_SUB).pack(pady=(0, 5))

        self.canvas_scroll = tk.Canvas(self.frame_ctrl, borderwidth=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.frame_ctrl, orient="vertical", command=self.canvas_scroll.yview)
        self.frame_legend_list = tk.Frame(self.canvas_scroll)

        self.canvas_scroll.create_window((0,0), window=self.frame_legend_list, anchor="nw")
        self.canvas_scroll.configure(yscrollcommand=self.scrollbar.set)
        self.canvas_scroll.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.frame_legend_list.bind("<Configure>", lambda e: self.canvas_scroll.configure(scrollregion=self.canvas_scroll.bbox("all")))

        # ウィンドウ表示を最優先し、初期描画処理を50ミリ秒後に遅延実行
        self.master.after(50, self.show_initial_guide_table)

    def on_mouse_wheel_zoom(self, event):
        """Ctrl + マウスホイールでスライダーを動かし、ズームを実行する"""
        current_zoom = self.scale_zoom.get()
        step = 10  # 1回スクロールしたときの変化量(%)

        if hasattr(event, 'delta') and event.delta != 0:
            # Windows / Mac
            if event.delta > 0:
                new_zoom = current_zoom + step
            else:
                new_zoom = current_zoom - step
        elif hasattr(event, 'num'):
            # Linux (X11)
            if event.num == 4:
                new_zoom = current_zoom + step
            elif event.num == 5:
                new_zoom = current_zoom - step
        else:
            return

        # スライダーの制限範囲内 (30〜300) に収める
        new_zoom = max(30, min(new_zoom, 300))
        
        # スライダーの値を更新（自動的にapply_zoomが発火します）
        self.scale_zoom.set(new_zoom)

    def center_graph(self, event=None):
        canvas_width = self.graph_scroll_canvas.winfo_width()
        canvas_height = self.graph_scroll_canvas.winfo_height()
        interior_width = self.frame_canvas_interior.winfo_reqwidth()
        interior_height = self.frame_canvas_interior.winfo_reqheight()

        x_offset = max(0, (canvas_width - interior_width) // 2)
        y_offset = max(0, (canvas_height - interior_height) // 2)

        self.graph_scroll_canvas.coords(self.interior_id, x_offset, y_offset)
        self.graph_scroll_canvas.configure(scrollregion=self.graph_scroll_canvas.bbox("all"))

    def apply_zoom(self):
        zoom_factor = self.scale_zoom.get() / 100.0
        new_dpi = self.base_dpi * zoom_factor
        self.fig.set_dpi(new_dpi)
        
        fw, fh = self.fig.get_size_inches()
        self.canvas_widget.config(width=int(fw * new_dpi), height=int(fh * new_dpi))
        
        self.canvas.draw()
        self.frame_graph_container.update_idletasks()
        self.center_graph()

    def show_initial_guide_table(self):
        self.fig.clear()
        self.fig.set_size_inches(8.5, 5.5)
        
        zoom_factor = self.scale_zoom.get() / 100.0
        self.fig.set_dpi(self.base_dpi * zoom_factor)

        ax = self.fig.add_subplot(111)
        ax.axis('off')
        ax.text(0.5, 0.85, "【使い方】Excelでデータをコピーし、\nこの画面上で「Ctrl + V」を押してください。", 
                ha='center', va='center', fontsize=12, color='#333333', fontname="Yu Gothic", weight="bold")
        data = [
            ["温度 [°C]", "出力電圧 Vout [V]", "電流 ic [mA]", "周波数 f [MHz]"],
            ["-20", "0.0145", "1.53239", "3.0012439"],
            ["-10", "0.0145", "1.54010", "3.0012483"]
        ]
        table = ax.table(cellText=data, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8) 
        for (row, col), cell in table.get_celld().items():
            cell.set_text_props(fontname="Yu Gothic")
            cell.set_facecolor('white')  
            cell.set_edgecolor('#D9D9D9')  
            if row == 0: cell.set_text_props(weight='bold')
        
        dpi = self.fig.dpi
        self.canvas_widget.config(width=int(8.5 * dpi), height=int(5.5 * dpi))
        self.canvas.draw()
        self.center_graph() 

    def load_from_clipboard(self):
        try:
            df = pd.read_clipboard(sep='\t', header=None)
            self.setup_data_and_ui(df)
        except Exception as e:
            messagebox.showerror("エラー", f"データの読み込み中にエラーが発生しました:\n{e}")

    def setup_data_and_ui(self, df):
        processed_df, names = process_dataframe(df)
        if processed_df is None:
            messagebox.showerror("エラー", names)
            return
        self.df = processed_df
        self.axis_names = names

        for widget in self.frame_legend_list.winfo_children():
            widget.destroy()
        self.entry_widgets = []

        for i in range(1, len(names)):
            lbl_text = f"Y{i}軸 ({names[i]}):"
            tk.Label(self.frame_legend_list, text=lbl_text, font=FONT_GUI_SMALL).pack(anchor=tk.W, pady=(5, 0))
            entry = tk.Entry(self.frame_legend_list, width=25, font=FONT_GUI_REG)
            entry.pack(pady=(0, 5))
            self.entry_widgets.append(entry)
        
        self.update_plot()

    def update_plot(self):
        if self.df is None:
            return

        self.fig.clear()
        
        pw = self.scale_plot_w.get()
        ph = self.scale_plot_h.get()
        
        num_axes = len(self.axis_names) - 1
        user_offset_step = self.scale_offset.get() 
        offset_inch_per_axis = user_offset_step / 72.0
        
        left_margin = 1.0 + (max(0, num_axes - 1) * offset_inch_per_axis)
        right_margin = 0.5
        bottom_margin = 0.8
        top_margin = 0.5
        
        fw = pw + left_margin + right_margin
        fh = ph + bottom_margin + top_margin
        self.fig.set_size_inches(fw, fh, forward=True)
        
        zoom_factor = self.scale_zoom.get() / 100.0
        self.fig.set_dpi(self.base_dpi * zoom_factor)
        
        rect = [left_margin / fw, bottom_margin / fh, pw / fw, ph / fh]
        
        ax_base = self.fig.add_axes(rect)
        ax_base.set_facecolor('white')
        
        valid_x = self.df['col_0'].dropna()
        if not valid_x.empty:
            x_min, x_max = valid_x.min(), valid_x.max()
            x_margin = (x_max - x_min) * 0.03 if x_max != x_min else 1
            ax_base.set_xlim(x_min - x_margin, x_max + x_margin)
            
        ax_base.set_xlabel(self.axis_names[0], fontsize=12)
        ax_base.grid(True, color='#D9D9D9', linestyle='-', linewidth=0.75)

        lines = []
        last_ax = ax_base 

        for i in range(1, len(self.axis_names)):
            col_key = f'col_{i}'
            axis_name = self.axis_names[i]
            
            custom_name = self.entry_widgets[i-1].get().strip()
            legend_name = custom_name if custom_name else remove_unit(axis_name)
            
            color = COLOR_CYCLE[(i-1) % len(COLOR_CYCLE)]
            markers = ['o', 's', '^', 'D', 'v', 'x', '*', 'p']
            marker = markers[(i-1) % len(markers)]

            if i == 1:
                ax = ax_base
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_visible(True)
            else:
                ax = self.fig.add_axes(rect)
                ax.patch.set_visible(False)
                ax.xaxis.set_visible(False)
                
                for key in ['top', 'right', 'bottom']:
                    ax.spines[key].set_visible(False)
                
                ax.yaxis.set_label_position('left')
                ax.yaxis.set_ticks_position('left')
                
                current_offset_pts = user_offset_step * (i - 1)
                ax.spines['left'].set_position(('outward', current_offset_pts))
                ax.spines['left'].set_visible(True)

            ax.spines['left'].set_color('black')
            ax.yaxis.label.set_color('black')
            ax.tick_params(axis='y', colors='black', labelsize=11)

            last_ax = ax  

            valid_y = self.df[col_key].dropna()
            if valid_y.empty:
                continue
                
            ymin, ymax = get_nice_limits(valid_y.min(), valid_y.max(), NUM_TICKS)
            line = ax.plot(self.df['col_0'], self.df[col_key], color=color, 
                           marker=marker, markersize=6, linewidth=2, label=legend_name)
            lines += line
            
            ax.set_ylabel(axis_name, fontsize=12)
            ax.set_ylim(ymin, ymax)
            ax.set_yticks(np.linspace(ymin, ymax, NUM_TICKS))
            ax.tick_params(axis='y', labelsize=11)
            ax.ticklabel_format(useOffset=False, style='plain')

        if lines and self.var_show_legend.get():
            labels = [str(l.get_label()) for l in lines]
            if self.var_transparent_legend.get():
                leg = last_ax.legend(lines, labels, loc='best', frameon=False, prop={'size': 11})
            else:
                leg = last_ax.legend(lines, labels, loc='best', frameon=True, facecolor='white', framealpha=0.9, prop={'size': 11})
            leg.set_draggable(True)
        
        dpi = self.fig.dpi
        self.canvas_widget.config(width=int(fw * dpi), height=int(fh * dpi))
        
        self.canvas.draw()
        
        self.frame_graph_container.update_idletasks()
        self.center_graph()

# ==========================================
# 4. アプリケーション起動
# ==========================================
if __name__ == "__main__":
    NUM_TICKS = 6
    root = tk.Tk()
    app = GraphApp(root)
    root.mainloop()