from manim import *
import pandas as pd
import numpy as np
from pathlib import Path
import requests

FONT = "Droid Sans Fallback"

DATA_PATH = "students.csv"
AVATAR_DIR = Path("avatars")
ICON_DIR = Path("node_icons")
FAVOR_ICON_DIR = Path("favor_icons")
OUTPUT_DIR = Path("renders")
OUTPUT_DIR.mkdir(exist_ok=True)

class StudentGiftCard(Scene):
    def construct(self):
        self.camera.frame_height = 18
        self.camera.frame_width = 32

        df = pd.read_csv(DATA_PATH)
        for idx, row in df.iterrows():
            try:
                self.clear()
                self.render_student_card(row)
                self.wait(1.5)
            except Exception as e:
                print(f"[ERROR] Failed on {row['StudentName']}: {e}")

    def draw_path_with_icons(self, path_str, color=YELLOW):
        nodes = str(path_str).split("->")
        node_groups = []
        for node in nodes:
            circ = Circle(radius=0.4, color=color)
            node_text = Text(node, font_size=18, font=FONT)
            node_text.move_to(circ.get_center())
            node_group = VGroup(circ, node_text)
            node_groups.append(node_group)
            
        final_group = VGroup()
        for idx, group in enumerate(node_groups):
            if idx > 0:
                separator = Text(">", font_size=18, font=FONT)
                final_group.add(separator)
            final_group.add(group)
        final_group.arrange(RIGHT, buff=0.5)
        return final_group

    def render_student_card(self, row):
        # --- 左侧内容 ---
        title = Text(f"{row['StudentName']}", font_size=48, font=FONT)
        student_id = int(row['StudentID'])
        avatar_file = AVATAR_DIR / f"{student_id}.webp"

        if not avatar_file.exists():
            try:
                url = f"https://schaledb.com/images/student/collection/{student_id}.webp"
                response = requests.get(url)
                if response.status_code == 200:
                    with open(avatar_file, "wb") as f:
                        f.write(response.content)
                    print(f"[INFO] 成功下载ID为{student_id}的头像.")
                else:
                    print(f"[ERROR] 下载{student_id}头像失败，状态码：{response.status_code}")
            except Exception as e:
                print(f"[ERROR] 下载{student_id}头像时出现异常: {e}")

        if avatar_file.exists():
            avatar = ImageMobject(str(avatar_file)).scale(1.5)
        else:
            avatar = Text("No Avatar", font_size=24, font=FONT)

        name_avatar = Group(title, avatar).arrange(DOWN, buff=0.3)
        overall_text = Text(f"总体平均收益: {row['总收益']:.2f}", font_size=28, font=FONT)

        # 水平居中整体
        name_avatar.move_to(ORIGIN)
        overall_text.move_to(ORIGIN)
        left_group = Group(name_avatar, overall_text).arrange(DOWN, buff=0.5).move_to(ORIGIN)
        left_group.to_edge(LEFT, buff=0.5)

        # --- 右侧 ---
        tiers_group = VGroup()
        tier_colors = {1: YELLOW, 2: GREEN, 3: ORANGE}
        for tier in range(1, 4):
            revenue = row[f"节点{tier}收益"]
            tier_text = Text(f"Tier{tier} 平均收益: {revenue:.2f}", font_size=24, font=FONT)
            path_str = row[f"节点{tier}推荐顺序"]
            path_group = self.draw_path_with_icons(path_str, color=tier_colors[tier])
            tier_info = VGroup(tier_text, path_group).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
            tiers_group.add(tier_info)
        tiers_group.arrange(DOWN, aligned_edge=LEFT, buff=0.8)

        favor_icon_names = {
            "20好感礼物数": "Cafe_Interaction_Gift_01.png",
            "40好感礼物数": "Cafe_Interaction_Gift_02.png",
            "60好感礼物数": "Cafe_Interaction_Gift_03.png",
            "120好感礼物数": "Cafe_Interaction_Gift_02.png",
            "180好感礼物数": "Cafe_Interaction_Gift_03.png",
            "240好感礼物数": "Cafe_Interaction_Gift_04.png",
        }
        favor_categories = ["20好感礼物数", "40好感礼物数", "60好感礼物数", 
                            "120好感礼物数", "180好感礼物数", "240好感礼物数"]
        favor_items = []
        for favor in favor_categories:
            icon_name = favor_icon_names.get(favor, f"{favor}.png")
            icon_path = FAVOR_ICON_DIR / icon_name
            if icon_path.exists():
                icon = ImageMobject(str(icon_path)).scale(1.3)
            else:
                icon = Text(favor, font_size=20, font=FONT)
            favor_value = row[favor]
            value_text = Text(f"{favor_value:.2f}", font_size=24, font=FONT)
            favor_item = Group(icon, value_text).arrange(DOWN, buff=0.1)
            favor_items.append(favor_item)

        gold_group = Group(*favor_items[:3]).arrange(RIGHT, buff=0.4)
        purple_group = Group(*favor_items[3:]).arrange(RIGHT, buff=0.4)

        gold_label = Text("金色礼物", font_size=20, font=FONT).set_color(GREY_A).scale(1.1)
        purple_label = Text("紫色礼物", font_size=20, font=FONT).set_color(GREY_A).scale(1.1)

        gold_group_with_label = Group(gold_label, gold_group).arrange(DOWN, buff=0.25)
        purple_group_with_label = Group(purple_label, purple_group).arrange(DOWN, buff=0.25)

        favors_group = Group(gold_group_with_label, purple_group_with_label).arrange(RIGHT, buff=0.8)
        right_group = Group(tiers_group, favors_group).arrange(DOWN, aligned_edge=LEFT, buff=1.0)
        right_group.to_edge(RIGHT, buff=0.5)

        final_layout = Group(left_group, right_group).arrange(RIGHT, buff=3.0).scale(1.6)

        self.play(FadeIn(final_layout, run_time=2.0))
