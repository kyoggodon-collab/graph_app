# ==========================================
# 1. 最低限のインポート（スプラッシュ画面用）と定数
# ==========================================
import tkinter as tk
from tkinter import messagebox

FONT_GUI_TITLE = ("Yu Gothic", 14, "bold")
FONT_GUI_SUB = ("Yu Gothic", 11, "bold")
FONT_GUI_REG = ("Yu Gothic", 11)
FONT_GUI_SMALL = ("Yu Gothic", 10)

COLOR_CYCLE = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5', '#70AD47', '#264478', '#997300']
NUM_TICKS = 6

# ==========================================
# 2. 補助関数
# ==========================================
def get_nice_limits(vmin, vmax, num_ticks=6):
    import math
    import pandas as pd
    if pd.isna(vmin) or pd.isna(vmax):
        return 0, 1
    if vmin == vmax: 
        return vmin - 1, vmax + 1
    
    margin = (vmax - vmin) * 0.02
    vmin_m = vmin - margin
    vmax_m = vmax + margin

    n_intervals = num_ticks - 1
    raw_step = (vmax_m - vmin_m) / n_intervals
    mag = math.floor(math.log10(raw_step))
    mag_pow = 10 ** mag
    norm_step = raw_step / mag_pow

    if norm_step <= 1.0: nice_norm_step = 1.0
    elif norm_step <= 1.2: nice_norm_step = 1.2
    elif norm_step <= 1.5: nice_norm_step = 1.5
    elif norm_step <= 2.0: nice_norm_step = 2.0
    elif norm_step <= 2.5: nice_norm_step = 2.5
    elif norm_step <= 3.0: nice_norm_step = 3.0
    elif norm_step <= 4.0: nice_norm_step = 4.0
    elif norm_step <= 5.0: nice_norm_step = 5.0
    elif norm_step <= 6.0: nice_norm_step = 6.0
    elif norm_step <= 8.0: nice_norm_step = 8.0
    else: nice_norm_step = 10.0

    nice_step = nice_norm_step * mag_pow
    nice_min = math.floor(vmin_m / nice_step) * nice_step
    nice_max = nice_min + nice_step * n_intervals

    steps_list = [1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    while nice_max < vmax_m:
        if nice_norm_step in steps_list:
            idx = steps_list.index(nice_norm_step)
            if idx < len(steps_list) - 1:
                nice_norm_step = steps_list[idx + 1]
            else:
                nice_norm_step = 1.0
                mag_pow *= 10
        else:
            nice_norm_step = 1.0
            mag_pow *= 10
            
        nice_step = nice_norm_step * mag_pow
        nice_min = math.floor(vmin_m / nice_step) * nice_step
        nice_max = nice_min + nice_step * n_intervals

    while nice_min + nice_step <= vmin_m and nice_max < vmax_m + nice_step:
        nice_min += nice_step
        nice_max += nice_step

    return nice_min, nice_max

def remove_unit(text):
    import re
    return re.sub(r'\s*[\[\(].*?[\]\)]', '', str(text)).strip()

def process_dataframe(df):
    import pandas as pd
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
        self.plot_toggles = []  
        self.marker_toggles = [] 
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

        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        self.fig = plt.Figure()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_canvas_interior)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(padx=30, pady=30)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_toolbar)
        self.toolbar.update()

        self.graph_scroll_canvas.bind("<Configure>", self.center_graph)
        self.frame_canvas_interior.bind("<Configure>", self.center_graph)

        # ==========================================
        # コントロールパネル全体の大枠（右側）
        # ==========================================
        self.frame_right_base = tk.Frame(self.frame_main, width=370) # パネル全体の幅を指定
        self.frame_right_base.pack(side=tk.RIGHT, fill=tk.Y)
        self.frame_right_base.pack_propagate(False) # 幅を固定して伸縮させない

        # 右側全体を覆うスクロール用キャンバス
        self.ctrl_canvas = tk.Canvas(self.frame_right_base, borderwidth=0, highlightthickness=0)
        self.ctrl_scrollbar = tk.Scrollbar(self.frame_right_base, orient="vertical", command=self.ctrl_canvas.yview)
        self.ctrl_canvas.configure(yscrollcommand=self.ctrl_scrollbar.set)
        
        self.ctrl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 実際の各操作ウィジェットを載せるフレーム
        self.frame_ctrl = tk.Frame(self.ctrl_canvas, padx=10, pady=10)
        self.ctrl_canvas.create_window((0, 0), window=self.frame_ctrl, anchor="nw")
        
        # 中身のサイズが変わったらスクロール領域を自動更新する
        self.frame_ctrl.bind("<Configure>", lambda e: self.ctrl_canvas.configure(scrollregion=self.ctrl_canvas.bbox("all")))

        # パネル上にカーソルがある時だけマウスホイールスクロールを有効にするバインド
        self.frame_right_base.bind("<Enter>", self._bind_panel_scroll)
        self.frame_right_base.bind("<Leave>", self._unbind_panel_scroll)

        # --- 以下、frame_ctrl へのウィジェット配置 ---
        self.btn_paste = tk.Button(self.frame_ctrl, text="📋 クリップボードから読込 (Ctrl+V)", 
                                   command=self.load_from_clipboard, bg="#4472C4", fg="white", font=FONT_GUI_SUB)
        self.btn_paste.pack(pady=5, fill=tk.X)

        self.btn_update = tk.Button(self.frame_ctrl, text="🔄 グラフ再描画・更新", 
                                    command=self.update_plot, bg="#70AD47", fg="white", font=FONT_GUI_SUB)
        self.btn_update.pack(pady=5, fill=tk.X)
        
        self.btn_copy_img = tk.Button(self.frame_ctrl, text="📸 グラフ画像をコピー", 
                                      command=self.copy_graph_to_clipboard, bg="#ED7D31", fg="white", font=FONT_GUI_SUB)
        self.btn_copy_img.pack(pady=5, fill=tk.X)
        
        # ステータス通知用のラベル
        self.lbl_status = tk.Label(self.frame_ctrl, text="", font=FONT_GUI_SMALL)
        self.lbl_status.pack(pady=(0, 5))

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
        self.scale_offset.set(30)  
        self.scale_offset.pack(fill=tk.X, pady=(0, 5))
        
        # 目盛りの向き設定
        tk.Label(self.frame_ctrl, text="④ 目盛りの向き:", font=FONT_GUI_SMALL, fg="#2E8B57").pack(anchor=tk.W)
        self.var_tick_dir = tk.StringVar(value="in")
        self.frame_tick = tk.Frame(self.frame_ctrl)
        self.frame_tick.pack(anchor=tk.W, pady=(0, 5))
        tk.Radiobutton(self.frame_tick, text="内向き", variable=self.var_tick_dir, value="in", command=self.update_plot).pack(side=tk.LEFT)
        tk.Radiobutton(self.frame_tick, text="外向き", variable=self.var_tick_dir, value="out", command=self.update_plot).pack(side=tk.LEFT)

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
        tk.Label(self.frame_ctrl, text="◆ 各データの個別設定 ＆ 凡例名", font=FONT_GUI_SUB).pack(pady=(0, 5))

        # 以前キャンバスだった部分をシンプルなフレームに変更（親がスクロールするため）
        self.frame_legend_list = tk.Frame(self.frame_ctrl)
        self.frame_legend_list.pack(fill=tk.BOTH, expand=True)

        self._status_timer = None
        self.master.after(50, self.show_initial_guide_table)

    # --- 右側パネル全体用マウスホイールイベント ---
    def _bind_panel_scroll(self, event):
        self.ctrl_canvas.bind_all("<MouseWheel>", self._on_panel_mousewheel)
        self.ctrl_canvas.bind_all("<Button-4>", self._on_panel_mousewheel)
        self.ctrl_canvas.bind_all("<Button-5>", self._on_panel_mousewheel)

    def _unbind_panel_scroll(self, event):
        self.ctrl_canvas.unbind_all("<MouseWheel>")
        self.ctrl_canvas.unbind_all("<Button-4>")
        self.ctrl_canvas.unbind_all("<Button-5>")

    def _on_panel_mousewheel(self, event):
        import platform
        # Ctrlキー(ズーム用)が押されている場合はパネルスクロールさせない
        if hasattr(event, 'state') and (event.state & 0x0004): 
            return

        if platform.system() == 'Windows':
            self.ctrl_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif platform.system() == 'Darwin':
            self.ctrl_canvas.yview_scroll(int(-1 * event.delta), "units")
        else: # Linux
            if event.num == 4:
                self.ctrl_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.ctrl_canvas.yview_scroll(1, "units")
    # --------------------------------------------
        
    def show_status_message(self, message, color="#2E8B57"):
        self.lbl_status.config(text=message, fg=color)
        if self._status_timer is not None:
            self.master.after_cancel(self._status_timer)
        self._status_timer = self.master.after(3000, lambda: self.lbl_status.config(text=""))

    def on_mouse_wheel_zoom(self, event):
        current_zoom = self.scale_zoom.get()
        step = 10 
        new_zoom = current_zoom

        if hasattr(event, 'delta') and event.delta != 0:
            if event.delta > 0:
                new_zoom = current_zoom + step
            else:
                new_zoom = current_zoom - step
        elif hasattr(event, 'num'):
            if event.num == 4:
                new_zoom = current_zoom + step
            elif event.num == 5:
                new_zoom = current_zoom - step
        else:
            return

        new_zoom = max(30, min(new_zoom, 300))
        self.scale_zoom.set(new_zoom)

    def center_graph(self, _event=None):
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
        for (row, _col), cell in table.get_celld().items():
            cell.set_text_props(fontname="Yu Gothic")
            cell.set_facecolor('white')  
            cell.set_edgecolor('#D9D9D9')  
            if row == 0: cell.set_text_props(weight='bold')
        
        dpi = self.fig.dpi
        self.canvas_widget.config(width=int(8.5 * dpi), height=int(5.5 * dpi))
        self.canvas.draw()
        self.center_graph() 

    def load_from_clipboard(self):
        import pandas as pd
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
        self.plot_toggles = []
        self.marker_toggles = []

        for i in range(1, len(names)):
            var_visible = tk.BooleanVar(value=True)
            var_marker = tk.BooleanVar(value=True)
            self.plot_toggles.append(var_visible)
            self.marker_toggles.append(var_marker)

            lbl_text = f"Y{i}軸 ({names[i]}):"
            
            frame_lbl = tk.Frame(self.frame_legend_list)
            frame_lbl.pack(anchor=tk.W, pady=(5, 0))
            
            tk.Label(frame_lbl, text=lbl_text, font=FONT_GUI_SMALL).pack(side=tk.LEFT, padx=(5, 0))
            
            chk_vis = tk.Checkbutton(frame_lbl, text="表示", variable=var_visible, font=FONT_GUI_SMALL, command=self.update_plot)
            chk_vis.pack(side=tk.LEFT)

            chk_mark = tk.Checkbutton(frame_lbl, text="プロットを表示", variable=var_marker, font=FONT_GUI_SMALL, command=self.update_plot)
            chk_mark.pack(side=tk.LEFT, padx=(5, 0))
            
            entry = tk.Entry(self.frame_legend_list, width=25, font=FONT_GUI_REG)
            entry.pack(pady=(0, 10), padx=5, anchor=tk.W)
            self.entry_widgets.append(entry)
        
        self.update_plot()

    def update_plot(self):
        import numpy as np
        if self.df is None:
            return

        self.fig.clear()
        
        pw = self.scale_plot_w.get()
        ph = self.scale_plot_h.get()
        
        unique_axes_names = []
        for i in range(1, len(self.axis_names)):
            if self.plot_toggles[i-1].get():
                name = self.axis_names[i]
                if name not in unique_axes_names:
                    unique_axes_names.append(name)
        
        # --- 動的オフセットの計算開始 ---
        axis_limits = {}
        for i in range(1, len(self.axis_names)):
            if not self.plot_toggles[i-1].get():
                continue
            axis_name = self.axis_names[i]
            col_key = f'col_{i}'
            valid_y = self.df[col_key].dropna()
            if valid_y.empty:
                continue
            if axis_name not in axis_limits:
                axis_limits[axis_name] = {'min': valid_y.min(), 'max': valid_y.max()}
            else:
                axis_limits[axis_name]['min'] = min(axis_limits[axis_name]['min'], valid_y.min())
                axis_limits[axis_name]['max'] = max(axis_limits[axis_name]['max'], valid_y.max())

        axis_offsets = {}
        current_cumulative_offset = 0
        char_width_pts = 6.0  # 1文字あたりの幅（pt換算）
        
        # 以前のようにスライダーの値をそのまま「基本の固定幅」として取得
        user_offset_step = self.scale_offset.get()

        for i, axis_name in enumerate(unique_axes_names):
            if axis_name in axis_limits:
                ymin, ymax = get_nice_limits(axis_limits[axis_name]['min'], axis_limits[axis_name]['max'], NUM_TICKS)
                ticks = np.linspace(ymin, ymax, NUM_TICKS)
                
                # 最大文字数を取得
                max_len = 0
                for t in ticks:
                    s = f"{t:.5f}".rstrip('0').rstrip('.')
                    if len(s) > max_len:
                        max_len = len(s)
            else:
                max_len = 4

            axis_offsets[axis_name] = current_cumulative_offset
            
            # 【変更箇所】元の固定値（スライダー値）に、文字数分の動的な幅を加算する
            current_cumulative_offset += user_offset_step + (max_len * char_width_pts)

        dynamic_left_margin_inch = (current_cumulative_offset + 30) / 72.0
        left_margin = max(1.0, dynamic_left_margin_inch)
        
        right_margin = 0.5
        bottom_margin = 0.8
        top_margin = 0.5
        
        fw = pw + left_margin + right_margin
        fh = ph + bottom_margin + top_margin
        self.fig.set_size_inches(fw, fh, forward=True)
        # --- 動的オフセットの計算終了 ---
        
        zoom_factor = self.scale_zoom.get() / 100.0
        self.fig.set_dpi(self.base_dpi * zoom_factor)
        
        rect = (left_margin / fw, bottom_margin / fh, pw / fw, ph / fh)
        
        ax_base = self.fig.add_axes(rect)
        ax_base.set_facecolor('white')
        
        valid_x = self.df['col_0'].dropna()
        if not valid_x.empty:
            x_min, x_max = valid_x.min(), valid_x.max()
            x_margin = (x_max - x_min) * 0.03 if x_max != x_min else 1
            ax_base.set_xlim(x_min - x_margin, x_max + x_margin)
            
        ax_base.set_xlabel(self.axis_names[0], fontsize=12)
        ax_base.grid(True, color='#D9D9D9', linestyle='-', linewidth=0.75)
        
        tick_dir = self.var_tick_dir.get()
        ax_base.tick_params(axis='x', direction=tick_dir, labelsize=11)

        lines = []
        y_axes_dict = {}     
        unique_axis_count = 0
        last_ax = ax_base 

        for i in range(1, len(self.axis_names)):
            if not self.plot_toggles[i-1].get():
                continue
            
            col_key = f'col_{i}'
            axis_name = self.axis_names[i]
            
            custom_name = self.entry_widgets[i-1].get().strip()
            legend_name = custom_name if custom_name else remove_unit(axis_name)
            
            color = COLOR_CYCLE[(i-1) % len(COLOR_CYCLE)]
            
            if self.marker_toggles[i-1].get():
                markers = ['o', 's', '^', 'D', 'v', 'x', '*', 'p']
                marker = markers[(i-1) % len(markers)]
            else:
                marker = 'None'  
            
            if axis_name not in y_axes_dict:
                unique_axis_count += 1
                if unique_axis_count == 1:
                    ax = ax_base
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    ax.spines['left'].set_visible(True)
                else:
                    ax = self.fig.add_axes(rect, sharex=ax_base)
                    ax.patch.set_visible(False)
                    ax.xaxis.set_visible(False)
                    
                    for key in ['top', 'right', 'bottom']:
                        ax.spines[key].set_visible(False)
                    
                    ax.yaxis.set_label_position('left')
                    ax.yaxis.set_ticks_position('left')
                    
                    # ここで事前計算した動的オフセットを適用
                    current_offset_pts = axis_offsets[axis_name]
                    ax.spines['left'].set_position(('outward', current_offset_pts))
                    ax.spines['left'].set_visible(True)

                    ax.spines['left'].set_color('black')
                    ax.yaxis.label.set_color('black')

                if axis_name in axis_limits:
                    ymin, ymax = get_nice_limits(axis_limits[axis_name]['min'], axis_limits[axis_name]['max'], NUM_TICKS)
                    ax.set_ylim(ymin, ymax)
                    ax.set_yticks(np.linspace(ymin, ymax, NUM_TICKS))
                
                ax.set_ylabel(axis_name, fontsize=12)
                ax.tick_params(axis='y', colors='black', labelsize=11, direction=tick_dir)
                ax.ticklabel_format(useOffset=False, style='plain')

                y_axes_dict[axis_name] = ax
            else:
                ax = y_axes_dict[axis_name]

            last_ax = ax  

            valid_y = self.df[col_key].dropna()
            if valid_y.empty:
                continue
            
            line = ax.plot(self.df['col_0'], self.df[col_key], color=color, 
                           marker=marker, markersize=6, linewidth=2, label=legend_name)
            lines += line

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
    
    def copy_graph_to_clipboard(self):
        import platform
        import os
        import io
        import tempfile
        import subprocess
        import ctypes
        if self.df is None:
            messagebox.showwarning("警告", "コピーするグラフがありません。")
            return

        try:
            system = platform.system()

            if system == 'Windows':
                from ctypes import wintypes 
                try:
                    from PIL import Image
                except ImportError:
                    messagebox.showerror("エラー", "画像コピー機能を使うには「Pillow」ライブラリが必要です。\nコマンドプロンプトで『pip install Pillow』を実行してください。")
                    return
                
                png_output = io.BytesIO()
                self.fig.savefig(png_output, format='png', dpi=300, bbox_inches='tight')
                png_output.seek(0)
                
                raw_img = Image.open(png_output)
                img = raw_img.convert("RGB")
                
                bmp_output = io.BytesIO()
                img.save(bmp_output, format="BMP")
                bmp_data = bmp_output.getvalue()
                
                png_output.close()
                bmp_output.close()
                
                dib_data = bmp_data[14:]
                
                GMEM_MOVEABLE = 0x0002
                CF_DIB = 8
                
                kernel32 = ctypes.windll.kernel32
                user32 = ctypes.windll.user32
                msvcrt = ctypes.cdll.msvcrt
                
                kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
                
                kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
                kernel32.GlobalLock.restype = wintypes.LPVOID
                
                kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
                kernel32.GlobalUnlock.restype = wintypes.BOOL
                
                user32.OpenClipboard.argtypes = [wintypes.HWND]
                user32.OpenClipboard.restype = wintypes.BOOL
                
                user32.EmptyClipboard.argtypes = []
                user32.EmptyClipboard.restype = wintypes.BOOL
                
                user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
                user32.SetClipboardData.restype = wintypes.HANDLE
                
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = wintypes.BOOL
                
                msvcrt.memcpy.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
                msvcrt.memcpy.restype = ctypes.c_void_p
                
                if not user32.OpenClipboard(None):
                    raise RuntimeError("クリップボードを開けませんでした。")
                    
                try:
                    user32.EmptyClipboard()
                    
                    h_img_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_data))
                    if not h_img_mem:
                        raise RuntimeError("メモリの確保に失敗しました。")
                        
                    p_img_mem = kernel32.GlobalLock(h_img_mem)
                    msvcrt.memcpy(p_img_mem, dib_data, len(dib_data))
                    kernel32.GlobalUnlock(h_img_mem)
                    
                    if not user32.SetClipboardData(CF_DIB, h_img_mem):
                        raise RuntimeError("クリップボードへのデータセットに失敗しました。")
                finally:
                    user32.CloseClipboard()
                    
            elif system == 'Darwin':
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    temp_path = tmp.name
                self.fig.savefig(temp_path, format='png', dpi=300, bbox_inches='tight')
                cmd = f'osascript -e \'set the clipboard to (read (POSIX file "{temp_path}") as TIFF picture)\''
                subprocess.run(cmd, shell=True, check=True)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            else:
                self.show_status_message("⚠️ ご利用のOSでは未サポートです", color="red")
                return

            self.show_status_message("✅ 画像をクリップボードにコピーしました！")

        except Exception as e:
            messagebox.showerror("エラー", f"画像のコピー中にエラーが発生しました:\n{e}")

# ==========================================
# 4. アプリケーション起動 ＆ スプラッシュ画面
# ==========================================
if __name__ == "__main__":
    # ----------------------------------------
    # ① メインウィンドウを生成し、一時的に非表示(withdraw)にする
    # ----------------------------------------
    root = tk.Tk()
    root.withdraw() 

    # ----------------------------------------
    # ② スプラッシュ画面を Toplevel (子ウィンドウ) として作成
    # ----------------------------------------
    splash = tk.Toplevel(root)
    splash.overrideredirect(True) # タイトルバーなしの枠にする
    splash.attributes('-topmost', True) # 最前面に表示
    
    # 画面中央に配置
    splash_w, splash_h = 420, 160
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = int((screen_w / 2) - (splash_w / 2))
    y = int((screen_h / 2) - (splash_h / 2))
    splash.geometry(f"{splash_w}x{splash_h}+{x}+{y}")
    
    # スプラッシュ画面のデザイン
    splash.configure(bg="#2B579A") 
    tk.Label(splash, text="多軸対応2Dグラフ描画ツール 起動中...", font=("Yu Gothic", 16, "bold"), bg="#2B579A", fg="white").pack(expand=True, pady=(25, 0))
    tk.Label(splash, text="ライブラリを読み込んでいます。\nしばらくお待ちください...", font=("Yu Gothic", 10), bg="#2B579A", fg="white").pack(expand=True, pady=(0, 25))
    
    # 強制的に画面を描画
    splash.update()

    # ----------------------------------------
    # ③ スプラッシュ表示中に重いライブラリを読み込む
    # ----------------------------------------
    import os
    import io
    import tempfile
    import subprocess
    import platform
    import ctypes

    import numpy as np
    import pandas as pd

    import matplotlib
    matplotlib.use('TkAgg')  
    import matplotlib.pyplot as plt

    # 高DPI対応
    if platform.system() == 'Windows':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # Matplotlib 初期設定
    plt.rcParams['font.family'] = 'Yu Mincho'  
    plt.rcParams['axes.unicode_minus'] = False  
    plt.rcParams['savefig.dpi'] = 200  
    plt.rcParams['savefig.bbox'] = 'tight'  

    # ----------------------------------------
    # ④ 読み込み完了後、メイン画面を構築してスプラッシュを消す
    # ----------------------------------------
    app = GraphApp(root)
    
    splash.destroy() # 起動中画面を閉じる
    root.deiconify() # 隠していたメインウィンドウを表示する
    
    # メインアプリの開始
    root.mainloop()