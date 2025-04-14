import json
import csv
import math
from itertools import combinations
import numpy as np

DEFAULT_YIELD_50 = 30
DEFAULT_YIELD_51 = 120

EXTRA_TAGS = ["BC", "Bc", "ew"]


def get_default_yield(gift_id):
    try:
        gid = int(gift_id)
    except Exception:
        return 0
    if 5000 <= gid < 5100:
        return DEFAULT_YIELD_50
    elif 5100 <= gid < 5200:
        return DEFAULT_YIELD_51
    else:
        return 0


def get_student_tags(student):
    return student.get("FavorItemTags", []) + student.get("FavorItemUniqueTags", [])


def compute_gift_recommendations(student, items, flag=False):
    student_tags = get_student_tags(student) + EXTRA_TAGS
    recs = []
    for item in items.values():
        if "Tags" not in item or "ExpValue" not in item:
            continue
        extra_count = sum(1 for tag in item["Tags"] if tag in EXTRA_TAGS)
        matching = [tag for tag in item["Tags"] if tag in student_tags]
        match_count = min(len(matching), 3)
        exp = item["ExpValue"] * (1 + match_count)
        if (match_count - extra_count) > 0 or flag:
            recs.append({"gift": item, "exp": exp, "grade": match_count + 1})
    recs.sort(key=lambda x: x["exp"], reverse=True)
    return recs


def build_student_fav_mapping(student, items):
    recs = compute_gift_recommendations(student, items, flag=False)
    mapping = {}
    for rec in recs:
        gid = rec["gift"].get("Id")
        if gid is not None:
            mapping[gid] = max(mapping.get(gid, 0), rec["exp"])
    return mapping


def compute_candidate_group_reward(group_data, student_fav):
    items = group_data.get("Items", [])
    total_chance = sum(item.get("Chance", 0) for item in items if item.get("Type") == "Item")
    if total_chance == 0:
        return {key: 0.0 for key in ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]}

    result = {key: 0.0 for key in ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]}
    for item in items:
        if item.get("Type") != "Item":
            continue
        chance = item.get("Chance", 0)
        amt = (item.get("AmountMin", 1) + item.get("AmountMax", 1)) / 2.0
        gid = item.get("Id")
        reward = student_fav.get(gid, 0)
        if reward == 0:
            reward = get_default_yield(gid)
        contrib = chance * amt * reward
        result["ExpectedReward"] += contrib
        for g in [30, 40, 60, 120, 180, 240]:
            if abs(reward - g) < 1e-3:
                result[f"G{g}"] += chance * amt
                break
    return result


def compute_node_reward(node, student_fav, groups_data, total_prop_cn):
    tier = node.get("Tier")
    if tier is None or tier < 1 or tier > len(total_prop_cn):
        return {k: 0.0 for k in ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]}

    groups_list = node.get("Groups", [])
    total_weight = sum(g.get("Weight", 0) for g in groups_list)
    if total_weight == 0:
        return {k: 0.0 for k in ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]}

    result = {k: 0.0 for k in ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]}
    for g in groups_list:
        norm = g.get("Weight", 0) / total_weight
        group_result = compute_candidate_group_reward(groups_data.get(str(g.get("GroupId")), {}), student_fav)
        for k in result:
            result[k] += norm * group_result[k]
    return result


def weighted_combinations_expected_max_eff(candidates, k):
    keys = ["ExpectedReward", "G30", "G40", "G60", "G120", "G180", "G240"]
    result = {key: 0.0 for key in keys}

    prob_arr = np.array([0.0] + [c["NodeProb"] for c in candidates])
    p_accu = np.cumsum(prob_arr)
    p_no = (1 - p_accu) ** k
    for i in range(len(candidates)):
        delta = p_no[i] - p_no[i + 1]
        for key in keys:
            result[key] += delta.item() * candidates[i][key]
    return result


def compute_tier_expected(student_fav, crafting_data, groups_data, total_prop_cn, tier):
    nodes_list = []
    for node in crafting_data.get("Nodes", []):
        if node.get("Tier") == tier:
            reward_info = compute_node_reward(node, student_fav, groups_data, total_prop_cn)
            node_prob = node.get("Property", 0) / total_prop_cn[tier - 1] if total_prop_cn[tier - 1] != 0 else 0
            nodes_list.append({
                "NodeID": node.get("Id", "N/A"),
                "NodeName": node.get("NameCn") or node.get("NameZh") or "N/A",
                "ExpectedReward": reward_info["ExpectedReward"],
                "NodeProb": node_prob,
                "G30": reward_info["G30"],
                "G40": reward_info["G40"],
                "G60": reward_info["G60"],
                "G120": reward_info["G120"],
                "G180": reward_info["G180"],
                "G240": reward_info["G240"]
            })
    if not nodes_list:
        return 0.0, [], []
    n = len(nodes_list)
    candidates_sorted = sorted(nodes_list, key=lambda x: x["ExpectedReward"], reverse=True)
    k = 5 if n >= 5 else n
    tier_expected_result = weighted_combinations_expected_max_eff(candidates_sorted, k)
    tier_expected = tier_expected_result["ExpectedReward"]
    choices_sorted = sorted([n for n in nodes_list if n["ExpectedReward"] > 0], key=lambda x: x["ExpectedReward"], reverse=True)
    return tier_expected, nodes_list, choices_sorted, tier_expected_result


def compute_expected_exp_per_stone(student, items, crafting_data, groups_data):
    student_fav = build_student_fav_mapping(student, items)
    total_prop_cn = crafting_data.get("TotalProp", {}).get("cn", [])
    tier_best = {}
    tier_choices = {}
    tier_nodes_all = {}
    tier_expected_results = {}
    overall = 0.0
    for t in [1, 2, 3]:
        best_val, nodes_list, choices_sorted, tier_expected_result = compute_tier_expected(student_fav, crafting_data, groups_data, total_prop_cn, t)
        tier_best[t] = best_val
        tier_choices[t] = choices_sorted
        tier_nodes_all[t] = nodes_list
        tier_expected_results[t] = tier_expected_result
        overall += best_val
    return overall, tier_best, tier_choices, tier_nodes_all, tier_expected_results


def main():
    with open("students.min.json", "r", encoding="utf-8") as f:
        students_data = json.load(f)
    with open("items.min.json", "r", encoding="utf-8") as f:
        items_data = json.load(f)
    with open("crafting.min.json", "r", encoding="utf-8") as f:
        crafting_data = json.load(f)
    with open("groups.min.json", "r", encoding="utf-8") as f:
        groups_data = json.load(f)

    final_output = []

    for student_id, student in students_data.items():
        student_name = student.get("Name", "Unknown")
        overall_expected, tier_best, tier_choices, tier_nodes, tier_expected_result = compute_expected_exp_per_stone(student, items_data, crafting_data, groups_data)

        gift_top4_order_tier1 = "None"
        gift_top4_order_tier2 = "None"
        gift_top4_order_tier3 = "None"

        for t in [1, 2, 3]:
            sorted_nodes = sorted(tier_nodes[t], key=lambda x: x["ExpectedReward"], reverse=True)
            top4 = [node for node in sorted_nodes if node["ExpectedReward"] > 0][:4]
            if t == 2:
                top4 = []
                flag = False
                for i, node in enumerate(sorted_nodes):
                    if node["ExpectedReward"] > 0:
                        if abs(node["ExpectedReward"] - DEFAULT_YIELD_50) <= 0.03 and not flag:
                            flag = True
                            node_ = node.copy()
                            node_['NodeName'] = "其它花"
                            for j in range(i + 1, len(sorted_nodes)):
                                if abs(node["ExpectedReward"] - DEFAULT_YIELD_50) > 0.03: break
                                node_j = sorted_nodes[j]
                                for jk, jv in node_j.items():
                                    if jk not in ['NodeName', 'ExpectedReward', 'G30']:
                                        node_[jk] += jv
                            top4.append(node_)
                        elif abs(node["ExpectedReward"] - DEFAULT_YIELD_50) > 0.03:
                            top4.append(node)
                        if len(top4) == 4:
                            break
            if top4:
                top4_names = "->".join(str(node["NodeName"]) for node in top4)
                if t == 1:
                    gift_top4_order_tier1 = top4_names
                elif t == 2:
                    gift_top4_order_tier2 = top4_names
                elif t == 3:
                    gift_top4_order_tier3 = top4_names

        agg_gift_30 = sum(tier_expected_result[t]["G30"] for t in [1, 2, 3])
        agg_gift_40 = sum(tier_expected_result[t]["G40"] for t in [1, 2, 3])
        agg_gift_60 = sum(tier_expected_result[t]["G60"] for t in [1, 2, 3])
        agg_gift_120 = sum(tier_expected_result[t]["G120"] for t in [1, 2, 3])
        agg_gift_180 = sum(tier_expected_result[t]["G180"] for t in [1, 2, 3])
        agg_gift_240 = sum(tier_expected_result[t]["G240"] for t in [1, 2, 3])

        final_output.append({
            "StudentID": student_id,
            "StudentName": student_name,
            "Tier1_Best": f"{tier_best.get(1, 0):.4f}",
            "Tier2_Best": f"{tier_best.get(2, 0):.4f}",
            "Tier3_Best": f"{tier_best.get(3, 0):.4f}",
            "OverallExpected": f"{overall_expected:.4f}",
            "GiftCount_30": f"{agg_gift_30:.4f}",
            "GiftCount_40": f"{agg_gift_40:.4f}",
            "GiftCount_60": f"{agg_gift_60:.4f}",
            "GiftCount_120": f"{agg_gift_120:.4f}",
            "GiftCount_180": f"{agg_gift_180:.4f}",
            "GiftCount_240": f"{agg_gift_240:.4f}",
            "GiftTop4ChoiceNodeOrderTier1": gift_top4_order_tier1,
            "GiftTop4ChoiceNodeOrderTier2": gift_top4_order_tier2,
            "GiftTop4ChoiceNodeOrderTier3": gift_top4_order_tier3
        })

    header = ["StudentID", "StudentName", "Tier1_Best", "Tier2_Best", "Tier3_Best", "OverallExpected",
              "GiftCount_30", "GiftCount_40", "GiftCount_60", "GiftCount_120", "GiftCount_180", "GiftCount_240",
              "GiftTop4ChoiceNodeOrderTier1", "GiftTop4ChoiceNodeOrderTier2", "GiftTop4ChoiceNodeOrderTier3"]

    print("\n最终汇总结果：")
    print("\t".join(header))
    for row in final_output:
        row_values = [str(row[col]) for col in header]
        print("\t".join(row_values))

    with open("students.csv", "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=header)
        writer.writeheader()
        for row in final_output:
            writer.writerow(row)

    print("\n最终结果已保存至 students.csv")


if __name__ == "__main__":
    main()